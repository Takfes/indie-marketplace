#!/usr/bin/env python3
"""SessionStart hook: nudge about partially configured credential-bearing
tools, without ever reading or printing a credential value.

Self-contained on purpose (see shared/resolver.py's own docstring for the
same rationale) — this lives directly in plugins/essentials/scripts/, which
build.py never regenerates for this plugin, so it carries its own read-only
copy of the store/catalog-reading logic instead of importing across a
plugin boundary into skills/secrets-manager/.

Presence only: every check below is a truthy/falsy test on a resolved
value, discarded immediately after the test. No value is ever held past
that test, logged, or printed.

Must never block session start: every failure mode here (missing store,
unreadable installed_plugins.json, malformed catalog.json, ...) is
swallowed and results in silent, empty output and exit 0.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

STORE_ENV_VAR = "INDIE_MARKETPLACE_HOME"
PROFILE_ENV_VAR = "INDIE_PROFILE"
DEFAULT_STORE_DIR = ".indie-marketplace"
BASE_PROFILE = "base"


def _claude_config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))


def _store_root() -> Path:
    override = os.environ.get(STORE_ENV_VAR)
    return Path(override) if override else Path.home() / DEFAULT_STORE_DIR


def _load_profiles() -> dict:
    path = _store_root() / "profiles.json"
    if not path.exists():
        return {"profiles": {BASE_PROFILE: {"projects": [], "values": {}}}}
    return json.loads(path.read_text())


def _read_active() -> str | None:
    path = _store_root() / "active"
    if not path.exists():
        return None
    name = path.read_text().strip()
    return name or None


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


def _longest_project_match(profiles: dict, cwd: Path) -> str | None:
    best_name = None
    best_len = -1
    cwd_parts = cwd.parts
    for name, profile in profiles.items():
        for project in profile.get("projects", []):
            project_parts = Path(project).resolve().parts
            n = len(project_parts)
            if n > best_len and cwd_parts[:n] == project_parts:
                best_name, best_len = name, n
    return best_name


def _resolve_profile_name(profiles: dict, cwd: Path, env: dict) -> str:
    explicit = env.get(PROFILE_ENV_VAR)
    if explicit and explicit in profiles:
        return explicit

    matched = _longest_project_match(profiles, cwd)
    if matched:
        return matched

    active = _read_active()
    if active and active in profiles:
        return active

    return BASE_PROFILE


def _is_set(profiles: dict, profile_name: str, var_name: str) -> bool:
    values = profiles.get(profile_name, {}).get("values", {})
    if values.get(var_name):
        return True
    return bool(profiles.get(BASE_PROFILE, {}).get("values", {}).get(var_name))


def _read_hook_cwd() -> Path:
    raw = sys.stdin.read()
    hook_input = json.loads(raw) if raw.strip() else {}
    return Path(hook_input.get("cwd") or os.getcwd()).resolve()


def _find_partial_tools(cwd: Path) -> list[tuple[str, str, list[str]]]:
    """[(plugin, tool, [missing required var names])] for every installed,
    enabled tool that has at least one required variable set and at least
    one unset — silent otherwise (fully configured or untouched)."""
    profiles = _load_profiles().get("profiles", {})
    profile_name = _resolve_profile_name(profiles, cwd, os.environ)

    partial: list[tuple[str, str, list[str]]] = []
    for plugin_name, install_path in _installed_plugin_paths().items():
        catalog_file = install_path / ".claude-plugin" / "catalog.json"
        try:
            if not catalog_file.exists():
                continue
            entries = json.loads(catalog_file.read_text())
            for entry in entries:
                required = [v["name"] for v in entry.get("env", []) if v.get("required")]
                if not required:
                    continue
                missing = [name for name in required if not _is_set(profiles, profile_name, name)]
                if missing and len(missing) < len(required):
                    partial.append((plugin_name, entry.get("name", "?"), missing))
        except Exception:
            # One plugin's malformed catalog.json must not silence every
            # other plugin's legitimate nudge — skip just this one.
            continue
    return partial


def main() -> int:
    try:
        cwd = _read_hook_cwd()
        partial = _find_partial_tools(cwd)
    except Exception:
        return 0

    if not partial:
        return 0

    lines = ["Partially configured credentials detected:"]
    for plugin_name, tool_name, missing in partial:
        lines.append(f"- {plugin_name}/{tool_name} missing: {', '.join(missing)}")
    lines.append(
        "Run the secrets-manager skill (provided by the essentials plugin) to finish setting these up."
    )

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n".join(lines),
        }
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
