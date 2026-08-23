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
  ./build.py --plugin skillcraft  # build a single named plugin only

How it works:
  source: local     → copies skills/<name>/ into the plugin (full directory)
  source: community → git clone repo into a tmpdir, copy skill subdir into plugin
                      Uses cached plugin content if already built, unless --fetch.
  plugin `hooks:`   → same community fetch, but copies a hooks/ directory
                      verbatim into the plugin instead of a skill.
  plugin `mcp:`     → hand-authored, no fetch — writes a .mcp.json with
                      one mcpServers entry per declared server, plus a
                      .env.example template and a VS Code vscode-mcp.json.
  plugin `env:`     → env var names with no MCP server behind them (a CLI
                      tool a skill drives). Reaches .env.example only.
  plugin `deps:`    → CLI tools a skill drives with no MCP server and no
                      env var either — validates the shape and writes them
                      verbatim to deps.json for the toolchain-doctor skill.
  `skills:`/`deps:` entries → may also carry their own `env:` map, same
                      shape as an `mcp:` entry's `env:`.
  plugin `catalog: true` → writes catalog.json: one {name, type, env}
                      object per mcp:/skills:/deps: entry, env listing
                      names only — for later tooling to consume.
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


def fetch_community_skill_group(skill: dict, plugin_dir: Path) -> None:
    """
    Fetch every skill directory found directly under a wildcard `path`.

    Triggered when bundles.yaml's `path` ends in `/*` (or is just `*` for
    the repo root). Every immediate subdirectory under that path containing
    a SKILL.md is copied into the plugin as its own skill, named after its
    folder — one clone covers the whole group.

    Unlike single-skill entries, group entries always re-clone: there is no
    way to know what's inside the folder (and thus decide what's "cached")
    without cloning first.
    """
    label = skill["name"]
    repo = skill.get("repo", "").strip()
    raw_path = skill.get("path", "").strip()
    parent = raw_path.rstrip("/")[:-1].rstrip("/")  # strip trailing "*"

    if not repo:
        err(f"{label} — community skill missing `repo:` in bundles.yaml")
        sys.exit(1)

    print(f"  Cloning {repo} (group: {parent or '.'}) ...")
    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo, str(tmpdir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            err(f"{label} — git clone failed")
            if result.stderr.strip():
                err(f"  {result.stderr.strip()}")
            sys.exit(1)

        base = tmpdir / parent if parent else tmpdir
        if not base.is_dir():
            err(f"{label} — group path '{parent}' not found in {repo}")
            sys.exit(1)

        found = sorted(
            d for d in base.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
        )
        if not found:
            err(f"{label} — no SKILL.md found directly under '{parent}' in {repo}")
            sys.exit(1)

        for src in found:
            skill_name = src.name
            dest = plugin_dir / skill_name
            shutil.copytree(
                src,
                dest,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".git"),
                dirs_exist_ok=True,
            )
            (dest / "SOURCE.md").write_text(
                f"# Source\n\n"
                f"- **Repo:** {repo}\n"
                f"- **Path:** `{parent}/{skill_name}`\n"
                f"- **Fetched:** {date.today()}\n",
                encoding="utf-8",
            )
            ok(f"{skill_name}  (community, fetched via group '{label}')")


def fetch_community_skill(skill: dict, plugin_dir: Path, fetch: bool) -> None:
    """
    Fetch a community skill by git-cloning its repo and copying the skill
    subdirectory directly into the plugin.

    bundles.yaml fields:
      repo  — GitHub (or any git) URL to clone
      path  — subdirectory inside the repo (defaults to skill name).
              End path in "/*" (or use "*" alone) to fetch every skill
              directory found directly under it instead of a single skill —
              see fetch_community_skill_group.

    No CLI tool dependency. No intermediate cache location. Files land exactly
    at plugins/<plugin>/<skill>/ — nothing in between.
    """
    name = skill["name"]
    raw_path = skill.get("path", name).strip()
    if raw_path.rstrip("/") == "*" or raw_path.rstrip("/").endswith("/*"):
        fetch_community_skill_group(skill, plugin_dir)
        return

    dest = plugin_dir / name
    already_cached = (dest / "SKILL.md").exists()

    if already_cached and not fetch:
        ok(f"{name}  (community, cached — run --fetch to update)")
        return

    repo = skill.get("repo", "").strip()
    path = raw_path

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


def fetch_community_hooks(hooks_cfg: dict, plugin_dir: Path, fetch: bool) -> None:
    """
    Fetch a plugin's hooks/ directory by git-cloning its repo and copying
    the hooks subdirectory verbatim into the plugin.

    bundles.yaml fields (under a plugin's `hooks:` block):
      repo  — git URL to clone
      path  — subdirectory inside the repo (defaults to "hooks")

    Cache-aware like a single community skill: skips re-cloning if the
    plugin already has a populated hooks/ directory, unless fetch=True.
    """
    repo = hooks_cfg.get("repo", "").strip()
    path = hooks_cfg.get("path", "hooks").strip()
    dest = plugin_dir / "hooks"
    already_cached = dest.is_dir() and any(dest.iterdir())

    if already_cached and not fetch:
        ok("hooks  (community, cached — run --fetch to update)")
        return

    if not repo:
        err("hooks — plugin's `hooks:` block missing `repo:` in bundles.yaml")
        sys.exit(1)

    print(f"  Cloning {repo} (hooks) ...")
    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo, str(tmpdir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            if already_cached:
                warn("hooks — clone failed, using cached copy")
                if result.stderr.strip():
                    warn(f"  {result.stderr.strip()}")
                return
            err("hooks — git clone failed")
            if result.stderr.strip():
                err(f"  {result.stderr.strip()}")
            sys.exit(1)

        src = tmpdir / path
        if not src.is_dir():
            err(f"hooks — path '{path}' not found in {repo}")
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
    ok("hooks  (community, fetched)")


def validate_deps(plugin: dict) -> None:
    """
    Validate a plugin's `deps:` block — CLI tools its skills invoke directly
    that have no MCP server behind them. Every entry needs at least `command`,
    the executable the toolchain-doctor skill looks for on PATH.
    """
    for entry in plugin.get("deps") or []:
        if not entry.get("command"):
            err(f"{plugin['name']} — a `deps:` entry is missing required `command`")
            sys.exit(1)


def write_deps_json(plugin: dict, plugin_dir: Path) -> None:
    """
    Generate a plugin's deps.json from its `deps:` block in bundles.yaml.

    Read directly off each installed plugin's own directory by the
    toolchain-doctor skill, which is stdlib-only and has no YAML parser —
    this is plain JSON so it can read the catalog without one, for plugins
    from any marketplace, not just this one.
    """
    deps = [
        {k: v for k, v in entry.items() if k in ("command", "label", "install", "manual")}
        for entry in plugin["deps"]
    ]
    (plugin_dir / ".claude-plugin" / "deps.json").write_text(
        json.dumps(deps, indent=2) + "\n", encoding="utf-8"
    )
    ok("deps.json")


def write_mcp_json(plugin: dict, plugin_dir: Path) -> None:
    """
    Generate a plugin's .mcp.json from its `mcp:` block in bundles.yaml.

    bundles.yaml fields (per entry, no `community` fetch variant — these
    are hand-authored against the upstream MCP package):
      name    — server key under mcpServers
      command — executable to run
      args    — list of CLI args (defaults to [])
      env     — optional map of required env var names. Only the names
                are used; each becomes "${NAME}" in .mcp.json so Claude
                Code resolves it from the user's shell environment.
    """
    mcp_servers = {}
    for entry in plugin["mcp"]:
        name = entry["name"]
        server = {
            "command": entry["command"],
            "args": entry.get("args", []),
        }
        env = entry.get("env")
        if env:
            server["env"] = {var: f"${{{var}}}" for var in env}
        mcp_servers[name] = server

    (plugin_dir / ".mcp.json").write_text(
        json.dumps({"mcpServers": mcp_servers}, indent=2) + "\n", encoding="utf-8"
    )
    ok(".mcp.json")


def write_env_example(plugin: dict, plugin_dir: Path) -> None:
    """
    Generate a plugin's .env.example from every env var name it declares —
    one group per `mcp:`/`skills:`/`deps:` entry that needs vars, plus one
    for the plugin's top-level `env:` block (credentials for a CLI tool with
    no entry of its own to carry them).

    Names are emitted verbatim as declared in bundles.yaml, with empty values —
    this is a template, never a secret store. Real values live in a hand-kept
    .env that build.py neither reads nor writes, so this file is always safe
    to overwrite wholesale.
    """
    groups = [
        (entry["name"], entry["env"])
        for entry in plugin.get("mcp") or []
        if entry.get("env")
    ]
    groups += [
        (entry["name"], entry["env"])
        for entry in plugin.get("skills") or []
        if entry.get("env")
    ]
    groups += [
        (entry.get("label") or entry["command"], entry["env"])
        for entry in plugin.get("deps") or []
        if entry.get("env")
    ]
    if plugin.get("env"):
        groups.append((f"{plugin['name']} CLI tools", plugin["env"]))

    scope = "plugin" if plugin.get("env") else "plugin's MCP servers"
    lines = [
        f"# Environment variables for the {plugin['name']} {scope}.",
        "# Generated by build.py — copy to .env and fill in values.",
        "",
    ]

    for label, env in groups:
        if len(groups) > 1:
            lines.append(f"# {label}")
        lines.extend(f"{var}=" for var in env)
        lines.append("")

    if not groups:
        lines.append("# No MCP server in this plugin requires an environment variable.")

    content = "\n".join(lines).rstrip("\n") + "\n"
    (plugin_dir / ".env.example").write_text(content, encoding="utf-8")
    ok(".env.example")


def write_vscode_mcp_json(plugin: dict, plugin_dir: Path) -> None:
    """
    Generate a plugin's vscode-mcp.json from the same `mcp:` block.

    VS Code's format differs from Claude Code's: servers live under `servers`
    (not `mcpServers`), and secrets are never inlined as plaintext ${VAR} —
    each declared env var becomes a `promptString` entry in the top-level
    `inputs` array, referenced from the server as ${input:<id>}. The `inputs`
    key is omitted entirely when no server declares an env var.
    """
    inputs: list[dict] = []
    servers = {}

    for entry in plugin["mcp"]:
        name = entry["name"]
        server = {
            "type": "stdio",
            "command": entry["command"],
            "args": entry.get("args", []),
        }
        env = entry.get("env") or {}
        if env:
            server["env"] = {}
            for var in env:
                input_id = f"{name}-{var.lower()}"
                inputs.append(
                    {
                        "type": "promptString",
                        "id": input_id,
                        "description": var,
                        "password": True,
                    }
                )
                server["env"][var] = f"${{input:{input_id}}}"
        servers[name] = server

    config: dict = {}
    if inputs:
        config["inputs"] = inputs
    config["servers"] = servers

    (plugin_dir / "vscode-mcp.json").write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )
    ok("vscode-mcp.json")


def write_catalog_json(plugin: dict, plugin_dir: Path) -> None:
    """
    Generate a plugin's catalog.json — one entry per `mcp:`/`skills:`/`deps:`
    item, naming it, its type, and which env var names it needs (names only,
    never values). Only written for a plugin declaring `catalog: true` in
    bundles.yaml.
    """
    catalog = [
        {"name": entry["name"], "type": "mcp", "env": list(entry.get("env") or {})}
        for entry in plugin.get("mcp") or []
    ]
    catalog += [
        {"name": entry["name"], "type": "skill", "env": list(entry.get("env") or {})}
        for entry in plugin.get("skills") or []
    ]
    catalog += [
        {
            "name": entry.get("label") or entry["command"],
            "type": "cli",
            "env": list(entry.get("env") or {}),
        }
        for entry in plugin.get("deps") or []
    ]

    (plugin_dir / ".claude-plugin" / "catalog.json").write_text(
        json.dumps(catalog, indent=2) + "\n", encoding="utf-8"
    )
    ok("catalog.json")


# ---------------------------------------------------------------------------
# Plugin builder
# ---------------------------------------------------------------------------

def build_plugin(plugin: dict, owner: dict, fetch: bool, fetch_only: bool = False) -> None:
    """
    Build a plugin directory from its skill (and optional hooks) definitions.

    fetch_only=True  → only re-fetch community content; skip local copy and manifests.
    fetch=True       → re-fetch community content from upstream before copying.
    """
    name = plugin["name"]
    plugin_dir = PLUGINS_DIR / name
    claude_plugin_dir = plugin_dir / ".claude-plugin"

    action = "Fetching community skills in" if fetch_only else "Building plugin"
    print(f"\n{BOLD}{action}: {name}{RESET}")

    skills_dir = plugin_dir / "skills"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    claude_plugin_dir.mkdir(exist_ok=True)
    skills_dir.mkdir(exist_ok=True)

    for skill in plugin.get("skills", []):
        source = skill.get("source", "local")
        if source == "local":
            if not fetch_only:
                build_local_skill(skill, skills_dir)
        elif source == "community":
            fetch_community_skill(skill, skills_dir, fetch=fetch or fetch_only)
        else:
            err(f"{skill['name']} — unknown source type: {source}")
            sys.exit(1)

    hooks_cfg = plugin.get("hooks")
    if hooks_cfg:
        source = hooks_cfg.get("source", "community")
        if source == "community":
            fetch_community_hooks(hooks_cfg, plugin_dir, fetch=fetch or fetch_only)
        else:
            err(f"{name} — unknown hooks source type: {source}")
            sys.exit(1)

    if fetch_only:
        return

    has_credentials = (
        plugin.get("mcp")
        or plugin.get("env")
        or any(s.get("env") for s in plugin.get("skills") or [])
        or any(d.get("env") for d in plugin.get("deps") or [])
    )
    if has_credentials:
        write_env_example(plugin, plugin_dir)

    if plugin.get("mcp"):
        write_mcp_json(plugin, plugin_dir)
        write_vscode_mcp_json(plugin, plugin_dir)

    if plugin.get("deps"):
        validate_deps(plugin)
        write_deps_json(plugin, plugin_dir)

    if plugin.get("catalog"):
        write_catalog_json(plugin, plugin_dir)

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

def _plugin_manifest_entry(p: dict) -> dict:
    """Build a single plugin entry for marketplace.json."""
    return {
        "name": p["name"],
        "description": p.get("description", ""),
        "version": p.get("version", "0.1.0"),
        "source": f"./plugins/{p['name']}",
    }


def write_marketplace(config: dict) -> None:
    MARKETPLACE_FILE.parent.mkdir(exist_ok=True)
    mp = config["marketplace"]
    plugins = config.get("plugins", [])

    manifest = {
        "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
        "name": mp["name"],
        "description": mp.get("description", ""),
        "owner": mp["owner"],
        "plugins": [_plugin_manifest_entry(p) for p in plugins],
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
            "  ./build.py --plugin skillcraft       build one plugin, use cache\n"
            "  ./build.py --plugin skillcraft --fetch       fetch + build one plugin\n"
            "  ./build.py --plugin skillcraft --fetch-only  fetch community for one plugin\n"
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
