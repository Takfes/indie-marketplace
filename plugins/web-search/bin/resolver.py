#!/usr/bin/env python3
"""Resolve credential values for the active profile.

This file is copied verbatim into every credential-bearing plugin's bin/ by
build.py — it must stay a single self-contained script with no imports
beyond the standard library and no dependency on any other file in this
repository (see shared/indie_store.py for the reusable, non-copied version
of the storage read/write contract).

Usage: resolver.py NAME [NAME...]

  A trailing '?' on a name marks it optional (e.g. ZOTERO_API_KEY?);
  everything else is required. Prints one KEY=VALUE line per resolved
  name to stdout. Exits non-zero, with one stderr line per missing
  required name, if any required name is unset.

Profile resolution order:
  $INDIE_PROFILE
  -> the profile whose projects[] entry is the longest path-segment
     prefix of realpath($PWD)
  -> the contents of $INDIE_MARKETPLACE_HOME/active (default ~/.indie-marketplace/active)
  -> "base"

Value resolution order, per name:
  profiles[profile].values[NAME] -> profiles["base"].values[NAME] -> unset
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


def _store_root() -> Path:
    override = os.environ.get(STORE_ENV_VAR)
    return Path(override) if override else Path.home() / DEFAULT_STORE_DIR


def _load_profiles() -> dict:
    path = _store_root() / "profiles.json"
    if not path.exists():
        return {"version": 1, "profiles": {BASE_PROFILE: {"projects": [], "values": {}}}}
    return json.loads(path.read_text())


def _read_active() -> str | None:
    path = _store_root() / "active"
    if not path.exists():
        return None
    name = path.read_text().strip()
    return name or None


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


def resolve_profile_name(profiles: dict, cwd: Path, env: dict) -> str:
    explicit = env.get(PROFILE_ENV_VAR)
    if explicit:
        if explicit not in profiles:
            print(
                f"resolver: profile '{explicit}' set via ${PROFILE_ENV_VAR} does not exist",
                file=sys.stderr,
            )
            sys.exit(1)
        return explicit

    matched = _longest_project_match(profiles, cwd)
    if matched:
        return matched

    active = _read_active()
    if active and active in profiles:
        return active

    return BASE_PROFILE


def resolve_value(profiles: dict, profile_name: str, name: str) -> str | None:
    profile_values = profiles.get(profile_name, {}).get("values", {})
    value = profile_values.get(name)
    if value:
        return value
    base_values = profiles.get(BASE_PROFILE, {}).get("values", {})
    return base_values.get(name) or None


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: resolver.py NAME[?] [NAME[?] ...]", file=sys.stderr)
        return 2

    profiles = _load_profiles().get("profiles", {})
    profile_name = resolve_profile_name(profiles, Path.cwd().resolve(), os.environ)

    lines: list[str] = []
    missing: list[str] = []
    for raw in argv:
        optional = raw.endswith("?")
        name = raw[:-1] if optional else raw
        value = resolve_value(profiles, profile_name, name)
        if value:
            lines.append(f"{name}={value}")
        elif not optional:
            missing.append(name)

    if missing:
        for name in missing:
            print(
                f"resolver: {name} is not set for profile '{profile_name}' "
                "— run the secrets-manager skill to set it",
                file=sys.stderr,
            )
        return 1

    if lines:
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
