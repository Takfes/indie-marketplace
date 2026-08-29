#!/usr/bin/env python3
"""Value-blind status reporting for indie-marketplace credential profiles.

Every command here inspects catalog variable NAMES, profile STATE (via
server.build_profiles_view, itself value-blind — see #69), project PATHS,
and file PERMISSIONS. None of that requires reading a credential value, and
none of these commands do.

This file is copied into the plugin-setup skill's installed plugin
directory alongside its runtime dependencies (server.py, indie_store.py) by
build.py's build_local_skill — Python standard library only.

Usage:
  status.py unset [--profile NAME]   list catalog variables unset for a
                                      profile (default: the profile the
                                      current directory resolves to)
  status.py resolve [PATH]           show which profile PATH (default: cwd)
                                      resolves to, and why
  status.py doctor                   check for stale bound project paths,
                                      variables no installed plugin
                                      declares, and non-0600/0700 store
                                      permissions
"""
from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import indie_store  # noqa: E402
import server as secrets_server  # noqa: E402

PROFILE_ENV_VAR = "INDIE_PROFILE"


def _resolve_profile_name(profiles: dict, cwd: Path, env: dict) -> tuple[str, str]:
    """Same precedence as resolver.py's resolve_profile_name, but also
    reports which mechanism decided it."""
    explicit = env.get(PROFILE_ENV_VAR)
    if explicit:
        if explicit in profiles:
            return explicit, f"${PROFILE_ENV_VAR}={explicit}"
        return indie_store.BASE_PROFILE, f"${PROFILE_ENV_VAR}={explicit!r} does not exist, falling back to base"

    best_name = None
    best_len = -1
    cwd_parts = cwd.parts
    for name, profile in profiles.items():
        for project in profile.get("projects", []):
            project_parts = Path(project).resolve().parts
            n = len(project_parts)
            if n > best_len and cwd_parts[:n] == project_parts:
                best_name, best_len = name, n
    if best_name:
        matched_path = str(Path(*cwd_parts[:best_len]))
        return best_name, f"bound project path ({matched_path})"

    active = indie_store.read_active()
    if active and active in profiles:
        return active, "active file"

    return indie_store.BASE_PROFILE, "base fallback (no $INDIE_PROFILE, no path match, no active file)"


def cmd_resolve(args: argparse.Namespace) -> int:
    path = Path(args.path or os.getcwd()).resolve()
    profiles = indie_store.load_profiles().get("profiles", {})
    name, reason = _resolve_profile_name(profiles, path, os.environ)
    print(f"{path} -> profile '{name}' ({reason})")
    return 0


def cmd_unset(args: argparse.Namespace) -> int:
    profiles = indie_store.load_profiles().get("profiles", {})
    profile = args.profile
    if profile is None:
        profile, _ = _resolve_profile_name(profiles, Path.cwd().resolve(), os.environ)
    if profile not in profiles:
        print(f"status: unknown profile {profile!r}", file=sys.stderr)
        return 1

    state = secrets_server.build_profiles_view().get(profile, {}).get("values", {})
    unset = [
        (entry["plugin"], entry["name"], var["name"], var["required"])
        for entry in secrets_server.build_catalog()
        for var in entry.get("env", [])
        if state.get(var["name"]) == "unset"
    ]

    if not unset:
        print(f"profile '{profile}': every declared variable is set.")
        return 0

    print(f"profile '{profile}': unset variables")
    for plugin, tool, var, required in unset:
        tag = "required" if required else "optional"
        print(f"  {plugin}/{tool}: {var} ({tag})")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    data = indie_store.load_profiles()
    profiles = data.get("profiles", {})
    catalog_vars = secrets_server.catalog_var_names(secrets_server.build_catalog())
    problems: list[str] = []

    for name, profile in profiles.items():
        for project in profile.get("projects", []):
            if not Path(project).exists():
                problems.append(f"profile '{name}': bound project path does not exist: {project}")

    for name, profile in profiles.items():
        for var in profile.get("values", {}):  # keys only — never the values themselves
            if var not in catalog_vars:
                problems.append(f"profile '{name}': '{var}' is not declared by any installed plugin")

    root = indie_store.store_root()
    for rel, expected in ((indie_store.PROFILES_FILE, 0o600), (indie_store.ACTIVE_FILE, 0o600)):
        p = root / rel
        if p.exists():
            mode = stat.S_IMODE(p.stat().st_mode)
            if mode != expected:
                problems.append(f"{p} has mode {oct(mode)}, expected {oct(expected)}")
    if root.exists():
        mode = stat.S_IMODE(root.stat().st_mode)
        if mode != 0o700:
            problems.append(f"{root} has mode {oct(mode)}, expected 0o700")

    if not problems:
        print("doctor: no problems found.")
        return 0

    print(f"doctor: {len(problems)} problem(s) found")
    for problem in problems:
        print(f"  {problem}")
    return 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="status.py")
    sub = parser.add_subparsers(dest="command", required=True)

    p_unset = sub.add_parser("unset", help="list unset variables for a profile")
    p_unset.add_argument("--profile", default=None)
    p_unset.set_defaults(func=cmd_unset)

    p_resolve = sub.add_parser("resolve", help="show which profile a directory resolves to, and why")
    p_resolve.add_argument("path", nargs="?", default=None)
    p_resolve.set_defaults(func=cmd_resolve)

    p_doctor = sub.add_parser("doctor", help="check for stale paths, orphaned variables, and bad permissions")
    p_doctor.set_defaults(func=cmd_doctor)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
