#!/usr/bin/env python3
"""SessionStart hook: nudge about CLI binaries an installed plugin needs at
session start and that are genuinely missing from PATH.

Reporting only — this never runs an install command. bundles.yaml's own
header is explicit that `install:` is a suggestion, and both this hook and
`deps.py doctor` keep that contract absolute.

Separate from secrets-startup-check.py on purpose: different domain,
different failure modes, and a malformed credential store must not be able
to suppress a CLI nudge or vice versa. Self-contained for the same reason
that script is (see its docstring) — it lives in
plugins/essentials/scripts/, which build.py never regenerates, so it
carries its own read-only copy of the installed-plugin discovery rather
than importing across a plugin boundary into skills/secrets-manager/.

Nothing here reads a credential value; catalog.json's `type: "cli"` entries
carry command names and install hints only.

Must never block session start: every failure mode (missing
installed_plugins.json, malformed catalog.json, an unusable login shell)
is swallowed and results in silent, empty output and exit 0.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

SKIP_ENV_VAR = "INDIE_MARKETPLACE_SKIP_CLI_CHECK"

# The login-shell probe's own ceiling, well inside this hook's 5s timeout in
# hooks.json. `-lc` sources the profile that builds PATH and measures in tens
# of milliseconds; `-lic` additionally sources .zshrc (oh-my-zsh and friends)
# and measured ~4.5s on a normal machine — over the whole hook's budget on
# its own. Never use -lic here.
PROBE_TIMEOUT_SECONDS = 2
PROBE_SENTINEL = "__indie_probe_done__"


def _claude_config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))


def _enabled_plugin_keys() -> set[str]:
    path = _claude_config_dir() / "settings.json"
    data = json.loads(path.read_text())
    return {key for key, value in data.get("enabledPlugins", {}).items() if value}


def _installed_plugin_paths() -> dict[str, Path]:
    path = _claude_config_dir() / "plugins" / "installed_plugins.json"
    data = json.loads(path.read_text())
    if data.get("version") != 2:
        return {}

    enabled_keys = _enabled_plugin_keys()
    result: dict[str, Path] = {}
    for key, records in data.get("plugins", {}).items():
        if key not in enabled_keys or not records:
            continue
        newest = max(records, key=lambda r: r.get("lastUpdated", ""))
        install_path = newest.get("installPath")
        if install_path:
            result[key.split("@", 1)[0]] = Path(install_path)
    return result


# ---------------------------------------------------------------------------
# Presence check
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

    A hook does not inherit an interactive shell's PATH. Launched from a
    GUI or an IDE on macOS, Claude Code (and so this hook) runs under the
    bare launchd PATH, where /opt/homebrew/bin, ~/.local/bin and a version
    manager's shims are all absent — every command this repo declares
    resolves to nothing and the nudge becomes a permanent false alarm. One
    batched `$SHELL -lc` looks where the user's own shell looks.

    A probe that errors, times out, or does not run to completion proves
    nothing, and returns the empty set. Silence on uncertainty is the whole
    point: the probe failing is never itself a reason to nudge.
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
    """Two-stage PATH resolution. shutil.which() first — the only stage in
    the common, everything-present case — then one batched login-shell
    probe for whatever it missed."""
    unresolved = []
    for command in commands:
        found = shutil.which(command)
        if not found or _is_shadowed(found, install_roots):
            unresolved.append(command)
    if not unresolved:
        return set()
    return _probe_login_shell(unresolved, install_roots)


# ---------------------------------------------------------------------------
# Catalog reading
# ---------------------------------------------------------------------------


def _is_eagerly_required(entry: dict) -> bool:
    """Whether a `type: "cli"` catalog entry is worth nudging about.

    `source: "mcp"` means Claude Code launches a server needing this binary
    at every session start, whether or not the user calls a tool on it — a
    connection failure they see immediately, with nothing explaining it.
    `source: "deps"` means a skill shells out to it on first use, which
    already fails loudly and locally ("command not found: firecrawl"), so
    it stays out of the nudge and is reported by `deps.py doctor` instead.

    This one predicate is the whole eager/lazy policy: returning True for
    `"deps"` too widens the nudge to every declared CLI.
    """
    return entry.get("source") == "mcp"


def _required_clis(install_paths: dict[str, Path]) -> list[tuple[str, dict]]:
    """[(plugin, catalog entry)] for every eagerly-required CLI declared by
    an installed, enabled plugin."""
    found: list[tuple[str, dict]] = []
    for plugin_name, install_path in sorted(install_paths.items()):
        catalog_file = install_path / ".claude-plugin" / "catalog.json"
        try:
            entries = json.loads(catalog_file.read_text())
            for entry in entries:
                if entry.get("type") != "cli" or not _is_eagerly_required(entry):
                    continue
                if entry.get("command"):
                    found.append((plugin_name, entry))
        except Exception:
            # One plugin's malformed catalog.json must not silence every
            # other plugin's legitimate nudge — skip just this one.
            continue
    return found


def _format_lines(missing: list[tuple[str, dict]]) -> list[str]:
    lines = ["Missing CLI tools required by installed plugins:"]
    for plugin_name, entry in missing:
        command = entry["command"]
        label = Path(command).name if "/" in command else command
        detail = f"- {plugin_name}/{label}"
        required_by = [str(n) for n in entry.get("required_by") or []]
        if required_by:
            detail += f" — needed by {', '.join(required_by)}"
        lines.append(detail)
        if entry.get("install"):
            lines.append(f"    install: {entry['install']}")
        elif entry.get("manual"):
            lines.append(f"    install docs: {entry['manual']}")
        else:
            lines.append("    no declared install hint")
    lines.append(
        "These are suggestions — nothing was installed. Ask the secrets-manager skill "
        "(provided by the essentials plugin) for the full CLI report, including tools "
        "only needed on first use."
    )
    lines.append(f"Set {SKIP_ENV_VAR}=1 to silence this check.")
    return lines


def _find_missing() -> list[tuple[str, dict]]:
    install_paths = _installed_plugin_paths()
    declared = _required_clis(install_paths)
    if not declared:
        return []

    install_roots = list(install_paths.values())
    commands = sorted({entry["command"] for _, entry in declared})
    missing = _missing_commands(commands, install_roots)
    return [(plugin, entry) for plugin, entry in declared if entry["command"] in missing]


def main() -> int:
    if os.environ.get(SKIP_ENV_VAR) == "1":
        return 0
    try:
        sys.stdin.read()  # drained but unused: this check has no cwd dependence
        missing = _find_missing()
    except Exception:
        return 0

    if not missing:
        return 0

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(_format_lines(missing)),
        }
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
