#!/usr/bin/env python3
"""CLI dependency reporting for indie-marketplace plugins.

A sibling of status.py, not one of its subcommands: status.py answers
questions about the credential *store*, and a CLI-presence check is a
different domain with a different failure mode. What the two share is
discovery — this file imports server.py and reuses its build_catalog() and
_installed_plugin_paths(), exactly as status.py already does, so there is
no third copy of "which plugins are installed and enabled".

Reporting only: this never runs an install command. bundles.yaml's header
is explicit that `install:` is a suggestion, and the SessionStart hook
(plugins/essentials/scripts/cli-startup-check.py) keeps the same contract.
See docs/cli-installation-architecture.md.

Usage:
  deps.py doctor    report every CLI tool each installed, enabled plugin
                    declares, present or missing, with its install hint.
                    Exit 0 when nothing is missing, 1 otherwise.
"""
from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server as secrets_server  # noqa: E402

# Same ceiling and rationale as the SessionStart hook's probe — see
# cli-startup-check.py. `-lc`, never `-lic`.
PROBE_TIMEOUT_SECONDS = 2
PROBE_SENTINEL = "__indie_probe_done__"


# ---------------------------------------------------------------------------
# Presence check
#
# Deliberately duplicated with cli-startup-check.py, which is self-contained
# by design (it cannot import across a plugin boundary into this skill). Any
# change to the resolution rules belongs in both.
# ---------------------------------------------------------------------------


def _is_shadowed(found: str, install_roots: list[Path]) -> bool:
    """True when a PATH hit resolves inside an installed plugin's own tree.

    Claude Code puts every installed plugin's bin/ on PATH, and build.py
    writes a credential-bearing deps: entry's scoped launcher at
    bin/<command> — named exactly the command it wraps. Such a hit says
    nothing about whether the real binary exists.
    """
    try:
        resolved = Path(found).resolve()
    except OSError:
        return False
    for root in install_roots:
        try:
            if resolved.is_relative_to(root.resolve()):
                return True
        except OSError:
            continue
    return False


def _probe_login_shell(commands: list[str], install_roots: list[Path]) -> set[str]:
    """Of `commands`, the ones a non-interactive login shell also cannot
    find — i.e. the ones proven missing.

    A process spawned by Claude Code does not inherit an interactive
    shell's PATH; launched from a GUI or an IDE on macOS it runs under the
    bare launchd PATH, where /opt/homebrew/bin and ~/.local/bin are absent.
    One batched `$SHELL -lc` looks where the user's own shell looks.

    A probe that errors, times out, or does not run to completion proves
    nothing and returns the empty set — an unresolved command is never
    reported missing on the strength of a failed probe.
    """
    shell = os.environ.get("SHELL") or "/bin/sh"
    names = " ".join(shlex.quote(c) for c in commands)
    script = (
        f"for c in {names}; do "
        'p=$(command -v "$c" 2>/dev/null) || p=; '
        "printf '%s\\t%s\\n' \"$c\" \"$p\"; "
        f"done; printf '%s\\n' {shlex.quote(PROBE_SENTINEL)}"
    )
    try:
        result = subprocess.run(
            [shell, "-lc", script],
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return set()

    lines = result.stdout.splitlines()
    if PROBE_SENTINEL not in lines:
        return set()

    missing: set[str] = set()
    for line in lines:
        command, sep, found = line.partition("\t")
        if not sep or command not in commands:
            continue
        if not found or (found.startswith("/") and _is_shadowed(found, install_roots)):
            missing.add(command)
    return missing


def _missing_commands(commands: list[str], install_roots: list[Path]) -> set[str]:
    """Two-stage PATH resolution: shutil.which() first, then one batched
    login-shell probe for whatever it missed."""
    unresolved = []
    for command in commands:
        found = shutil.which(command)
        if not found or _is_shadowed(found, install_roots):
            unresolved.append(command)
    if not unresolved:
        return set()
    return _probe_login_shell(unresolved, install_roots)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _collect() -> dict[str, dict]:
    """command -> {command, install, manual, source, plugins} across every
    installed, enabled plugin's catalog.json, deduped by command: `npx` is
    one entry naming three plugins, not three entries.

    A command reached both eagerly (an mcp: server's own command) and
    lazily (a deps: entry) ranks as eager — that is when it is first
    needed. The first declared install hint wins; a later plugin's silence
    never erases it.
    """
    tools: dict[str, dict] = {}
    for entry in secrets_server.build_catalog():
        if entry.get("type") != "cli":
            continue
        command = entry.get("command") or entry.get("name")
        if not command:
            continue
        plugin = entry.get("plugin", "?")
        required_by = [str(n) for n in entry.get("required_by") or []]
        tool = tools.get(command)
        if tool is None:
            tool = tools[command] = {
                "command": command,
                "install": entry.get("install"),
                "manual": entry.get("manual"),
                "source": entry.get("source"),
                "plugins": [],
            }
        else:
            tool["install"] = tool["install"] or entry.get("install")
            tool["manual"] = tool["manual"] or entry.get("manual")
            if entry.get("source") == "mcp":
                tool["source"] = "mcp"
        label = f"{plugin} ({', '.join(required_by)})" if required_by else plugin
        tool["plugins"].append(label)
    return tools


def _print_group(title: str, note: str, tools: list[dict], missing: set[str]) -> None:
    print(title)
    print(f"  {note}")
    for tool in sorted(tools, key=lambda t: t["command"]):
        command = tool["command"]
        mark, state = ("✗", "missing") if command in missing else ("✓", "present")
        print(f"  {mark} {command}  {state} — {'; '.join(tool['plugins'])}")
        if command not in missing:
            continue
        if tool["install"]:
            print(f"      install: {tool['install']}")
        elif tool["manual"]:
            print(f"      install docs: {tool['manual']}")
        else:
            print("      no declared install hint — add a deps: entry to give it one")
    print()


def cmd_doctor(args: argparse.Namespace) -> int:
    tools = _collect()
    if not tools:
        print("deps doctor: no installed, enabled plugin declares a CLI tool.")
        return 0

    install_roots = list(secrets_server._installed_plugin_paths().values())
    missing = _missing_commands(sorted(tools), install_roots)

    eager = [t for t in tools.values() if t["source"] == "mcp"]
    lazy = [t for t in tools.values() if t["source"] != "mcp"]

    if eager:
        _print_group(
            "Required at session start",
            "MCP servers launch with the session, so these are needed whether or not you call a tool.",
            eager,
            missing,
        )
    if lazy:
        _print_group(
            "Required on first use",
            "A skill shells out to these; nothing breaks until you invoke it.",
            lazy,
            missing,
        )

    print("Presence on PATH only — a present `docker` says nothing about whether its")
    print("daemon is running or a plugin's image is built locally.")
    if not missing:
        print("deps doctor: every declared CLI tool is present.")
        return 0
    print(f"deps doctor: {len(missing)} tool(s) missing. Nothing was installed — install commands are suggestions.")
    return 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="deps.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_doctor = sub.add_parser("doctor", help="report which declared CLI tools are present or missing")
    p_doctor.set_defaults(func=cmd_doctor)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
