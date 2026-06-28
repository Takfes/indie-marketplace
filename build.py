#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["pyyaml"]
# ///
"""
build.py — Builds Claude Code plugins from bundles.yaml.

Usage:
  ./build.py              # build all plugins (community skills use cached content)
  ./build.py --fetch      # re-fetch all community skills from upstream, then build
  ./build.py --fetch-only # re-fetch community skills only, skip build
  ./build.py --plugin provision  # build a single named plugin only

How it works:
  source: local     → copies skills/<name>/ into the plugin (full directory)
  source: community → git clone repo into a tmpdir, copy skill subdir into plugin
                      Uses cached plugin content if already built, unless --fetch.
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent
SKILLS_DIR = ROOT / "skills"
PLUGINS_DIR = ROOT / "plugins"
BUNDLES_FILE = ROOT / "bundles.yaml"
MARKETPLACE_FILE = ROOT / ".claude-plugin" / "marketplace.json"

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}⚠{RESET} {msg}")


def err(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}")


def load_config() -> dict:
    with open(BUNDLES_FILE) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Skill builders
# ---------------------------------------------------------------------------

def build_local_skill(skill: dict, plugin_dir: Path) -> None:
    """Copy a local skill directory (full contents) into the plugin."""
    name = skill["name"]
    src = SKILLS_DIR / name
    dst = plugin_dir / name

    if not src.exists():
        err(f"{name} — local source not found: {src}")
        sys.exit(1)

    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
        dirs_exist_ok=True,
    )
    ok(f"{name}  (local)")


def _find_skill_in_clone(tmpdir: Path, name: str, path: str) -> Path | None:
    """
    Locate a skill directory inside a git clone.

    Tries in order:
      1. Exact path match: tmpdir / path
      2. Fuzzy match: any directory containing SKILL.md whose normalized name
         (lowercase, spaces/underscores → hyphens) equals the skill name.
    """
    exact = tmpdir / path
    if (exact / "SKILL.md").exists():
        return exact

    normalized_name = name.lower().replace(" ", "-").replace("_", "-")
    for skill_md in tmpdir.rglob("SKILL.md"):
        dir_name = skill_md.parent.name.lower().replace(" ", "-").replace("_", "-")
        if dir_name == normalized_name:
            return skill_md.parent

    return None


def fetch_community_skill(skill: dict, plugin_dir: Path, fetch: bool) -> None:
    """
    Fetch a community skill by git-cloning its repo and copying the skill
    subdirectory directly into the plugin.

    bundles.yaml fields:
      repo  — GitHub (or any git) URL to clone
      path  — subdirectory inside the repo (defaults to skill name)

    No CLI tool dependency. No intermediate cache location. Files land exactly
    at plugins/<plugin>/<skill>/ — nothing in between.
    """
    name = skill["name"]
    dest = plugin_dir / name
    already_cached = (dest / "SKILL.md").exists()

    if already_cached and not fetch:
        ok(f"{name}  (community, cached — run --fetch to update)")
        return

    repo = skill.get("repo", "").strip()
    path = skill.get("path", name).strip()

    if not repo:
        err(f"{name} — community skill missing `repo:` in bundles.yaml")
        sys.exit(1)

    print(f"  Cloning {repo} ...")
    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo, str(tmpdir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            if already_cached:
                warn(f"{name} — clone failed, using cached copy")
                if result.stderr.strip():
                    warn(f"  {result.stderr.strip()}")
                return
            err(f"{name} — git clone failed")

            if result.stderr.strip():
                err(f"  {result.stderr.strip()}")
            sys.exit(1)

        src = _find_skill_in_clone(tmpdir, name, path)
        if src is None:
            top_level = [d.name for d in tmpdir.iterdir() if d.is_dir() and not d.name.startswith(".")]
            err(f"{name} — path '{path}' not found in {repo}")
            err(f"  Top-level dirs: {top_level}")
            sys.exit(1)

        shutil.copytree(
            src,
            dest,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".git"),
            dirs_exist_ok=True,
        )

    (dest / "SOURCE.md").write_text(
        f"# Source\n\n"
        f"- **Repo:** {repo}\n"
        f"- **Path:** `{path}`\n"
        f"- **Fetched:** {date.today()}\n",
        encoding="utf-8",
    )
    ok(f"{name}  (community, fetched)")


# ---------------------------------------------------------------------------
# Plugin builder
# ---------------------------------------------------------------------------

def build_plugin(plugin: dict, owner: dict, fetch: bool, fetch_only: bool = False) -> None:
    """
    Build a plugin directory from its skill definitions.

    fetch_only=True  → only re-fetch community skills; skip local copy and manifests.
    fetch=True       → re-fetch community skills from upstream before copying.
    """
    name = plugin["name"]
    plugin_dir = PLUGINS_DIR / name
    claude_plugin_dir = plugin_dir / ".claude-plugin"

    action = "Fetching community skills in" if fetch_only else "Building plugin"
    print(f"\n{BOLD}{action}: {name}{RESET}")

    plugin_dir.mkdir(parents=True, exist_ok=True)
    claude_plugin_dir.mkdir(exist_ok=True)

    for skill in plugin.get("skills", []):
        source = skill.get("source", "local")
        if source == "local":
            if not fetch_only:
                build_local_skill(skill, plugin_dir)
        elif source == "community":
            fetch_community_skill(skill, plugin_dir, fetch=fetch or fetch_only)
        else:
            err(f"{skill['name']} — unknown source type: {source}")
            sys.exit(1)

    if fetch_only:
        return

    plugin_json = {
        "name": name,
        "description": plugin.get("description", ""),
        "version": plugin.get("version", "0.1.0"),
        "author": owner,
    }
    (claude_plugin_dir / "plugin.json").write_text(
        json.dumps(plugin_json, indent=2) + "\n", encoding="utf-8"
    )
    ok("plugin.json")


# ---------------------------------------------------------------------------
# Marketplace manifest
# ---------------------------------------------------------------------------

def write_marketplace(config: dict) -> None:
    MARKETPLACE_FILE.parent.mkdir(exist_ok=True)
    mp = config["marketplace"]
    plugins = config.get("plugins", [])

    manifest = {
        "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
        "name": mp["name"],
        "description": mp.get("description", ""),
        "owner": mp["owner"],
        "plugins": [
            {
                "name": p["name"],
                "description": p.get("description", ""),
                "version": p.get("version", "0.1.0"),
                "source": f"./plugins/{p['name']}",
            }
            for p in plugins
        ],
    }

    MARKETPLACE_FILE.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    ok("marketplace.json")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Claude Code plugins from bundles.yaml",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  ./build.py                          build all, use cached community skills\n"
            "  ./build.py --fetch                  re-fetch community, then build all\n"
            "  ./build.py --fetch-only             re-fetch community only, skip build\n"
            "  ./build.py --plugin provision       build one plugin, use cache\n"
            "  ./build.py --plugin provision --fetch       fetch + build one plugin\n"
            "  ./build.py --plugin provision --fetch-only  fetch community for one plugin\n"
        ),
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Re-fetch community skills from upstream, then build",
    )
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        dest="fetch_only",
        help="Re-fetch community skills only — skip local skill copy and manifest generation",
    )
    parser.add_argument(
        "--plugin",
        metavar="NAME",
        help="Operate on one named plugin only",
    )
    args = parser.parse_args()

    config = load_config()
    plugins = config.get("plugins", [])

    if args.plugin:
        plugins = [p for p in plugins if p["name"] == args.plugin]
        if not plugins:
            err(f"No plugin named '{args.plugin}' in bundles.yaml")
            sys.exit(1)

    PLUGINS_DIR.mkdir(exist_ok=True)

    owner = config["marketplace"].get("owner", {})
    for plugin in plugins:
        build_plugin(plugin, owner=owner, fetch=args.fetch, fetch_only=args.fetch_only)

    if not args.fetch_only:
        print(f"\n{BOLD}Writing marketplace manifest{RESET}")
        write_marketplace(config)
        print(f"\n{GREEN}{BOLD}✓ Build complete.{RESET}")
    else:
        print(f"\n{GREEN}{BOLD}✓ Community skills fetched.{RESET}")


if __name__ == "__main__":
    main()
