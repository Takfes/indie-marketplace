#!/usr/bin/env python3
"""
Report which runtimes and catalog dependencies the user's installed Claude
Code plugins need, and which of those are missing from PATH.

Stdlib only, and deliberately not a uv script — uv is one of the runtimes this
tool exists to detect the absence of.

  check_toolchain.py                        report only; never installs
  check_toolchain.py --install uv --yes     install one missing runtime
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

MACOS = sys.platform == "darwin"
HAS_BREW = bool(shutil.which("brew"))

# Executables a plugin's MCP server may declare as `command`, mapped to the
# runtime that provides them.
COMMAND_RUNTIME = {
    "npx": "node",
    "npm": "node",
    "node": "node",
    "uv": "uv",
    "uvx": "uv",
    "bun": "bun",
    "bunx": "bun",
    "docker": "docker",
    "python": "python",
    "python3": "python",
}

RUNTIMES = {
    "node": {
        "label": "Node.js (provides npx/npm)",
        "install": "brew install node" if MACOS and HAS_BREW else None,
        "manual": "https://nodejs.org/en/download",
    },
    "uv": {
        "label": "uv (Python package/tool runner)",
        "install": "curl -LsSf https://astral.sh/uv/install.sh | sh",
        "manual": "https://docs.astral.sh/uv/getting-started/installation/",
    },
    "bun": {
        "label": "Bun",
        "install": "curl -fsSL https://bun.sh/install | bash",
        "manual": "https://bun.sh/docs/installation",
    },
    "docker": {
        "label": "Docker",
        "install": None,
        "manual": "https://docs.docker.com/get-docker/",
    },
    "python": {
        "label": "Python 3",
        "install": None,
        "manual": "https://www.python.org/downloads/",
    },
}

INSTALLABLE = sorted(r for r, i in RUNTIMES.items() if i["install"])


def installed_plugins():
    """Installed, enabled plugins as reported by Claude Code itself."""
    try:
        out = subprocess.run(
            ["claude", "plugin", "list", "--json"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except FileNotFoundError:
        sys.exit("error: `claude` not found on PATH — run this from a shell where the Claude Code CLI is available.")
    except subprocess.CalledProcessError as e:
        sys.exit(f"error: `claude plugin list --json` failed:\n{e.stderr.strip()}")

    try:
        plugins = json.loads(out)
    except json.JSONDecodeError:
        sys.exit("error: could not parse `claude plugin list --json` — the CLI's output format may have changed.")
    if not isinstance(plugins, list):
        sys.exit("error: expected a list from `claude plugin list --json` — the CLI's output format may have changed.")

    return [p for p in plugins if p.get("enabled", True)]


def requirements(plugins):
    """{executable: [plugin id, ...]} declared across every plugin's MCP servers."""
    needs = {}
    for plugin in plugins:
        for server, spec in (plugin.get("mcpServers") or {}).items():
            command = spec.get("command")
            # A command given as a path or a ${VAR} ships with the plugin and is
            # resolved by Claude Code, not installed by the user — not our concern.
            if not command or os.sep in command or "${" in command:
                continue
            needs.setdefault(command, []).append(f"{plugin.get('id', '<unknown>')} ({server})")
    return needs


def plugin_deps(plugin):
    """
    A plugin's own catalog of non-MCP CLI dependencies, read from the
    deps.json that build.py writes next to its plugin.json (see bundles.yaml's
    `deps:` block). Returns [] for a plugin that never declared one — this
    catalog is fully optional, and most plugins from most marketplaces won't
    have it at all.
    """
    install_path = plugin.get("installPath")
    if not install_path:
        return []
    deps_file = Path(install_path) / ".claude-plugin" / "deps.json"
    if not deps_file.is_file():
        return []
    try:
        deps = json.loads(deps_file.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    return deps if isinstance(deps, list) else []


def catalog_requirements(plugins):
    """{command: [(plugin id, dep entry), ...]} declared across every plugin's deps.json."""
    needs = {}
    for plugin in plugins:
        for entry in plugin_deps(plugin):
            command = entry.get("command")
            if not command:
                continue
            needs.setdefault(command, []).append((plugin.get("id", "<unknown>"), entry))
    return needs


def missing_commands(needs):
    return {cmd for cmd in needs if not shutil.which(cmd)}


def report(needs, catalog_needs):
    missing = missing_commands(needs)

    if not needs:
        print("No installed plugin declares an MCP server, so no runtime is required.")
    else:
        print("Runtimes required by installed plugins:\n")
        for cmd in sorted(needs):
            mark = "missing" if cmd in missing else "ok"
            print(f"  [{mark:>7}] {cmd}")
            for user in needs[cmd]:
                print(f"            └─ {user}")
        print()

        if not missing:
            print("Everything needed is already on PATH. Nothing to install.")
        else:
            print("Missing — nothing has been installed:\n")
            seen = set()
            for cmd in sorted(missing):
                runtime = COMMAND_RUNTIME.get(cmd)
                if runtime is None:
                    print(f"  {cmd} — unrecognised runtime; install it however that tool documents.")
                    continue
                if runtime in seen:
                    continue
                seen.add(runtime)
                info = RUNTIMES[runtime]
                print(f"  {cmd} — {info['label']}")
                if info["install"]:
                    print(f"      ask the user to approve: {info['install']}")
                    print(f"      then run: python3 {sys.argv[0]} --install {runtime} --yes")
                else:
                    print(f"      no scripted install available; see {info['manual']}")

    print()
    catalog_missing = missing_commands(catalog_needs)

    if not catalog_needs:
        print("No installed plugin declares a catalog dependency (bundles.yaml `deps:`).")
        return

    print("Catalog dependencies required by installed plugins:\n")
    for cmd in sorted(catalog_needs):
        mark = "missing" if cmd in catalog_missing else "ok"
        print(f"  [{mark:>7}] {cmd}")
        for plugin_id, _entry in catalog_needs[cmd]:
            print(f"            └─ {plugin_id}")
    print()

    if not catalog_missing:
        print("Everything needed is already on PATH. Nothing to install.")
        return

    print("Missing — nothing has been installed:\n")
    for cmd in sorted(catalog_missing):
        _plugin_id, entry = catalog_needs[cmd][0]
        label = entry.get("label", cmd)
        print(f"  {cmd} — {label}")
        if entry.get("install"):
            print(f"      ask the user to approve: {entry['install']}")
        elif entry.get("manual"):
            print(f"      no scripted install available; see {entry['manual']}")
        else:
            print("      no install suggestion declared; install it however that tool documents.")


def install(runtime, assume_yes):
    info = RUNTIMES[runtime]
    print(f"About to install {info['label']} by running:\n\n    {info['install']}\n")

    if not assume_yes:
        if not sys.stdin.isatty():
            sys.exit(
                "Aborted — nothing installed. Ask the user to approve the exact command "
                f"above; once they have, re-run with --install {runtime} --yes"
            )
        try:
            answer = input("Proceed? [y/N] ")
        except (EOFError, KeyboardInterrupt):
            sys.exit("\nAborted — nothing installed.")
        if answer.strip().lower() not in ("y", "yes"):
            sys.exit("Aborted — nothing installed.")

    # pipefail so a failed curl in `curl … | sh` isn't masked by the shell's exit.
    sys.stdout.flush()
    result = subprocess.run(["bash", "-o", "pipefail", "-c", info["install"]])
    if result.returncode != 0:
        sys.exit(f"Install failed (exit {result.returncode}) — see {info['manual']}")
    print(f"\nInstall finished. If {runtime} still isn't found, open a new shell and re-run the report.")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--install",
        metavar="RUNTIME",
        choices=INSTALLABLE,
        help="install one runtime (%s), but only if an installed plugin needs it and it's missing."
        % ", ".join(INSTALLABLE),
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="confirm the install without a prompt. Pass only once the user has approved it.",
    )
    args = parser.parse_args()

    plugins = installed_plugins()
    needs = requirements(plugins)
    catalog_needs = catalog_requirements(plugins)

    if not args.install:
        report(needs, catalog_needs)
        return

    wanted = {COMMAND_RUNTIME.get(cmd) for cmd in missing_commands(needs)}
    if args.install not in wanted:
        sys.exit(
            f"Refusing to install {args.install}: no installed plugin needs it, or it's already "
            "on PATH. Run without --install to see the current report."
        )
    install(args.install, args.yes)


if __name__ == "__main__":
    main()
