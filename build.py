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
                      tool a skill drives). Reaches .env.example only. Each
                      name maps to null (required, undescribed) or a
                      {required, description} object.
  plugin `deps:`    → CLI tools a skill drives with no MCP server and no
                      env var either — validates the shape and writes them
                      verbatim to deps.json.
  `skills:`/`deps:` entries → may also carry their own `env:` map, same
                      shape as an `mcp:` entry's `env:`.
  credential-bearing  an `mcp:`/`deps:` entry declaring `env:` gets a
  entries           → generated wrapper (deps: a scoped launcher) in the
                      plugin's bin/, alongside a copy of shared/resolver.py.
                      The wrapper resolves and exports its declared vars,
                      then execs the real command — .mcp.json/vscode-mcp.json
                      point `command` at the wrapper (empty args, no `env`
                      block) instead of substituting `${VAR}` themselves.
                      An entry with no `env:` is unchanged and gets no
                      wrapper.
  plugin `catalog: true` → writes catalog.json: one {name, type, env}
                      object per mcp:/skills:/deps: entry, env listing one
                      {name, required, description} object per variable —
                      for later tooling to consume.
  duplicate env names → the same var name declared by more than one plugin
                      fails the build, across every non-fetch build
                      (including scoped `--plugin` ones).
  plugin `vendor:`  → whole-plugin vendoring: clones a third-party repo
                      and copies one of its plugin directories verbatim
                      into this plugin's root (manifest, LICENSE, NOTICE
                      and all), optionally pinned to a ref. Skips the
                      usual skill/hooks/mcp/deps/catalog dispatch and
                      plugin.json owner-stamping.
"""

import argparse
import json
import re
import shlex
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
RESOLVER_SRC = ROOT / "shared" / "resolver.py"

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


def fetch_vendor_plugin(vendor_cfg: dict, plugin_dir: Path, fetch: bool) -> None:
    """
    Vendor an entire third-party plugin: git-clone its repo and copy one of
    its plugin directories verbatim into this plugin's root — manifest,
    LICENSE, NOTICE, and all — unlike fetch_community_skill/
    fetch_community_hooks, which fetch at skill/hooks granularity into a
    fixed subfolder.

    bundles.yaml fields (under a plugin's `vendor:` block):
      repo — git URL to clone
      path — subdirectory inside the repo containing the plugin
      ref  — optional git tag/branch/sha to pin to (omit to track the
             default branch)

    Cache-aware like the other fetchers: skips re-cloning if the plugin's
    own .claude-plugin/plugin.json is already present, unless fetch=True.
    """
    repo = vendor_cfg.get("repo", "").strip()
    path = vendor_cfg.get("path", "").strip()
    ref = vendor_cfg.get("ref", "").strip()
    ref_label = f" @ {ref}" if ref else ""

    already_cached = (plugin_dir / ".claude-plugin" / "plugin.json").exists()
    if already_cached and not fetch:
        ok("vendored plugin  (cached — run --fetch to update)")
        return

    if not repo or not path:
        err("vendor — plugin's `vendor:` block missing `repo:` or `path:` in bundles.yaml")
        sys.exit(1)

    print(f"  Cloning {repo}{ref_label} (vendor: {path}) ...")
    with tempfile.TemporaryDirectory() as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        clone_cmd = ["git", "clone", "--depth", "1"]
        if ref:
            clone_cmd += ["--branch", ref]
        clone_cmd += [repo, str(tmpdir)]
        result = subprocess.run(clone_cmd, capture_output=True, text=True)

        if result.returncode != 0 and ref:
            # `ref` may be a bare sha, which a shallow --branch clone can't
            # resolve — fall back to a full clone and an explicit checkout.
            result = subprocess.run(
                ["git", "clone", repo, str(tmpdir)], capture_output=True, text=True
            )
            if result.returncode == 0:
                result = subprocess.run(
                    ["git", "-C", str(tmpdir), "checkout", ref],
                    capture_output=True,
                    text=True,
                )

        if result.returncode != 0:
            if already_cached:
                warn("vendor — clone failed, using cached copy")
                if result.stderr.strip():
                    warn(f"  {result.stderr.strip()}")
                return
            err("vendor — git clone failed")
            if result.stderr.strip():
                err(f"  {result.stderr.strip()}")
            sys.exit(1)

        src = tmpdir / path
        if not src.is_dir():
            err(f"vendor — path '{path}' not found in {repo}")
            sys.exit(1)

        shutil.copytree(
            src,
            plugin_dir,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".git"),
            dirs_exist_ok=True,
        )

    (plugin_dir / "SOURCE.md").write_text(
        f"# Source\n\n"
        f"- **Repo:** {repo}\n"
        f"- **Path:** `{path}`\n"
        f"- **Ref:** {ref or '(default branch)'}\n"
        f"- **Fetched:** {date.today()}\n",
        encoding="utf-8",
    )
    ok(f"vendored plugin  (fetched from {repo}{ref_label})")


def validate_deps(plugin: dict) -> None:
    """
    Validate a plugin's `deps:` block — CLI tools its skills invoke directly
    that have no MCP server behind them. Every entry needs at least `command`,
    the executable to look for on PATH.
    """
    for entry in plugin.get("deps") or []:
        if not entry.get("command"):
            err(f"{plugin['name']} — a `deps:` entry is missing required `command`")
            sys.exit(1)


def _env_declarations(plugin: dict) -> list[tuple[str, str]]:
    """List (var name, source label) for every env var a plugin declares."""
    decls = []
    for entry in plugin.get("mcp") or []:
        decls += [(var, f"mcp:{entry['name']}") for var in entry.get("env") or {}]
    for entry in plugin.get("skills") or []:
        decls += [(var, f"skills:{entry['name']}") for var in entry.get("env") or {}]
    for entry in plugin.get("deps") or []:
        decls += [(var, f"deps:{entry['command']}") for var in entry.get("env") or {}]
    decls += [(var, "env") for var in plugin.get("env") or {}]
    return decls


def validate_no_duplicate_env_vars(config: dict) -> None:
    """
    Fail the build if the same env var name is declared by more than one
    plugin. Variables are keyed globally by name, so a collision would make
    two plugins silently share one credential.
    """
    by_var: dict[str, list[tuple[str, str]]] = {}
    for plugin in config.get("plugins", []):
        for var, label in _env_declarations(plugin):
            by_var.setdefault(var, []).append((plugin["name"], label))

    for var, occurrences in by_var.items():
        plugin_names = {name for name, _ in occurrences}
        if len(plugin_names) > 1:
            where = ", ".join(f"{name} ({label})" for name, label in occurrences)
            err(f"env var '{var}' is declared by more than one plugin: {where}")
            sys.exit(1)


def write_deps_json(plugin: dict, plugin_dir: Path) -> None:
    """
    Generate a plugin's deps.json from its `deps:` block in bundles.yaml.

    Plain JSON, not YAML, so it can be read without a YAML parser — for
    plugins from any marketplace, not just this one.
    """
    deps = [
        {k: v for k, v in entry.items() if k in ("command", "install", "manual")}
        for entry in plugin["deps"]
    ]
    (plugin_dir / ".claude-plugin" / "deps.json").write_text(
        json.dumps(deps, indent=2) + "\n", encoding="utf-8"
    )
    ok("deps.json")


# ---------------------------------------------------------------------------
# Credential wrappers (bin/)
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
_PLACEHOLDER_SEARCH_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_ENV_ASSIGN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

_WRAPPER_HEADER = "#!/bin/sh\n# Generated by build.py — do not edit by hand.\nset -e\n"
_WRAPPER_RESOLVE = (
    'DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n'
    'RESOLVED=$("$DIR/resolver.py" {resolver_args}) || exit $?\n'
    "while IFS='=' read -r key value; do\n"
    '  [ -n "$key" ] && export "$key=$value"\n'
    "done <<EOF\n"
    "$RESOLVED\n"
    "EOF\n"
)


def credential_bearing_mcp_entries(plugin: dict) -> list[dict]:
    """mcp: entries needing a generated wrapper — those declaring env:."""
    return [entry for entry in plugin.get("mcp") or [] if entry.get("env")]


def credential_bearing_dep_entries(plugin: dict) -> list[dict]:
    """deps: entries needing a generated scoped launcher — those declaring env:."""
    return [entry for entry in plugin.get("deps") or [] if entry.get("env")]


def _resolver_args(env: dict | None) -> list[str]:
    """Build resolver.py's argv for one entry's declared env vars."""
    args = []
    for var, meta in (env or {}).items():
        required, _ = _normalize_env_var(meta)
        args.append(var if required else f"{var}?")
    return args


def _resolve_token(token: str, env_names: set[str]) -> str:
    """
    Translate one bundles.yaml command/arg string into a shell-quoted
    wrapper argv token. Every `${VAR}` placeholder it contains — whether
    the whole token (a positional arg, or the command itself) or embedded
    in a larger one (a docker volume mount, `-v ${VAR}:/path:ro`) —
    becomes the wrapper's own shell variable, safe because the wrapper
    exports the real value before this token is ever referenced. Literal
    text around a placeholder, and tokens with no placeholder at all, are
    escaped so they can't break out of the surrounding double quotes.
    """
    if not _PLACEHOLDER_SEARCH_RE.search(token):
        return shlex.quote(token)

    def escape(literal: str) -> str:
        return literal.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")

    parts = []
    pos = 0
    for m in _PLACEHOLDER_SEARCH_RE.finditer(token):
        parts.append(escape(token[pos : m.start()]))
        name = m.group(1)
        parts.append(f"${name}" if name in env_names else escape(m.group(0)))
        pos = m.end()
    parts.append(escape(token[pos:]))
    return '"' + "".join(parts) + '"'


def _wrapper_body(entry: dict) -> tuple[list[str], list[str]]:
    """
    Translate one credential-bearing entry's command+args into the exports
    and exec argv of its generated wrapper.

    Two bundles.yaml idioms carry a secret as a `NAME=${VAR}`-shaped
    string, which would otherwise land in the wrapper's own argv (visible
    via `ps`) once `${VAR}` is expanded:
      - a docker `-e NAME=${VAR}` pair → becomes bare `-e NAME`, which
        pulls NAME from the wrapper's own already-exported environment
        instead — renamed via an explicit export first when NAME != VAR.
      - `command: env NAME=${VAR} ... realcmd args` — bundles.yaml's way
        of setting env vars .mcp.json's own `env:` block can't express
        (see write_mcp_json) — becomes plain exports ahead of `realcmd`,
        dropping the `env` command entirely.
    Every other `${VAR}` placeholder (a positional arg, or the command
    itself) is inherently argv-visible by necessity — a filesystem path or
    similar — and is substituted in place via `_resolve_token`.

    Returns (exports, argv) — argv tokens are already shell-quoted.
    """
    env_names = set(entry.get("env") or {})
    exports: list[str] = []
    command = entry["command"]
    args = list(entry.get("args") or [])

    if command == "env":
        i = 0
        while i < len(args):
            m = _ENV_ASSIGN_RE.match(args[i])
            if not m:
                break
            name, value = m.groups()
            placeholder = _PLACEHOLDER_RE.match(value)
            if placeholder and placeholder.group(1) in env_names:
                var = placeholder.group(1)
                if var != name:
                    exports.append(f'export {name}="${var}"')
            else:
                exports.append(f"export {name}={shlex.quote(value)}")
            i += 1
        command = args[i]
        args = args[i + 1 :]

    argv = [_resolve_token(command, env_names)]
    i = 0
    while i < len(args):
        if args[i] == "-e" and i + 1 < len(args):
            m = _ENV_ASSIGN_RE.match(args[i + 1])
            if m:
                name, value = m.groups()
                placeholder = _PLACEHOLDER_RE.match(value)
                if placeholder and placeholder.group(1) in env_names:
                    var = placeholder.group(1)
                    if var != name:
                        exports.append(f'export {name}="${var}"')
                    argv += ["-e", shlex.quote(name)]
                    i += 2
                    continue
        argv.append(_resolve_token(args[i], env_names))
        i += 1

    return exports, argv


def _wrapper_script(entry: dict) -> str:
    """Render one credential-bearing mcp: entry's wrapper as POSIX shell."""
    exports, argv = _wrapper_body(entry)
    resolver_args = " ".join(shlex.quote(a) for a in _resolver_args(entry.get("env")))
    parts = [_WRAPPER_HEADER, _WRAPPER_RESOLVE.format(resolver_args=resolver_args)]
    parts += [f"{line}\n" for line in exports]
    parts.append(f"exec {' '.join(argv)}\n")
    return "".join(parts)


def _scoped_launcher_script(entry: dict) -> str:
    """
    Render one credential-bearing deps: entry's scoped launcher: it runs
    exactly entry['command'], forwarding the caller's own arguments, and
    accepts no substitute command — a general "run anything with these
    credentials" entry point would be a credential oracle for anything
    able to invoke it.
    """
    exports, _ = _wrapper_body(entry)
    resolver_args = " ".join(shlex.quote(a) for a in _resolver_args(entry.get("env")))
    parts = [_WRAPPER_HEADER, _WRAPPER_RESOLVE.format(resolver_args=resolver_args)]
    parts += [f"{line}\n" for line in exports]
    parts.append(f'exec {shlex.quote(entry["command"])} "$@"\n')
    return "".join(parts)


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def write_bin(plugin: dict, plugin_dir: Path) -> None:
    """
    Generate a plugin's bin/: a copy of shared/resolver.py plus one wrapper
    per credential-bearing mcp: entry and one scoped launcher per
    credential-bearing deps: entry. A plugin with neither gets no bin/ at
    all — the resolver travels only with the wrappers that need it, so a
    plugin installed alone still resolves its own credentials.
    """
    mcp_entries = credential_bearing_mcp_entries(plugin)
    dep_entries = credential_bearing_dep_entries(plugin)
    if not mcp_entries and not dep_entries:
        return

    bin_dir = plugin_dir / "bin"
    bin_dir.mkdir(exist_ok=True)
    shutil.copy2(RESOLVER_SRC, bin_dir / "resolver.py")
    (bin_dir / "resolver.py").chmod(0o755)

    for entry in mcp_entries:
        _write_executable(bin_dir / entry["name"], _wrapper_script(entry))
    for entry in dep_entries:
        _write_executable(bin_dir / entry["command"], _scoped_launcher_script(entry))

    ok("bin/")


def write_mcp_json(plugin: dict, plugin_dir: Path) -> None:
    """
    Generate a plugin's .mcp.json from its `mcp:` block in bundles.yaml.

    bundles.yaml fields (per entry, no `community` fetch variant — these
    are hand-authored against the upstream MCP package):
      name    — server key under mcpServers
      command — executable to run
      args    — list of CLI args (defaults to [])
      env     — optional map of env var metadata (see bundles.yaml header).
                An entry declaring env gets a generated wrapper in bin/
                (write_bin) that resolves and exports these before exec'ing
                the real command; here, command becomes the wrapper path
                with empty args and no env block — nothing left to resolve.
    """
    mcp_servers = {}
    for entry in plugin["mcp"]:
        name = entry["name"]
        if entry.get("env"):
            server = {"command": f"${{CLAUDE_PLUGIN_ROOT}}/bin/{name}", "args": []}
        else:
            server = {
                "command": entry["command"],
                "args": entry.get("args", []),
            }
        mcp_servers[name] = server

    (plugin_dir / ".mcp.json").write_text(
        json.dumps({"mcpServers": mcp_servers}, indent=2) + "\n", encoding="utf-8"
    )
    ok(".mcp.json")


def _normalize_env_var(meta: dict | None) -> tuple[bool, str | None]:
    """
    Normalize one `env:` value into (required, description).

    A `null` value (bundles.yaml's original shape) means required and
    undescribed. A mapping may override either field; both default to
    required: true, description: None.
    """
    if meta is None:
        return True, None
    return meta.get("required", True), meta.get("description")


def write_env_example(plugin: dict, plugin_dir: Path) -> None:
    """
    Generate a plugin's .env.example from every env var name it declares —
    one group per `mcp:`/`skills:`/`deps:` entry that needs vars, plus one
    for the plugin's top-level `env:` block (credentials for a CLI tool with
    no entry of its own to carry them).

    Names are emitted verbatim as declared in bundles.yaml, with empty values —
    this is a template, never a secret store. Real values live in a hand-kept
    .env that build.py neither reads nor writes, so this file is always safe
    to overwrite wholesale. Each variable's description (if any) and its
    required/optional state are emitted as a comment above it.
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
        (entry["command"], entry["env"])
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
        for var, meta in env.items():
            required, description = _normalize_env_var(meta)
            note = " ".join(p for p in (description, None if required else "(optional)") if p)
            if note:
                lines.append(f"# {note}")
            lines.append(f"{var}=")
        lines.append("")

    if not groups:
        lines.append("# No MCP server in this plugin requires an environment variable.")

    content = "\n".join(lines).rstrip("\n") + "\n"
    (plugin_dir / ".env.example").write_text(content, encoding="utf-8")
    ok(".env.example")


def write_vscode_mcp_json(plugin: dict, plugin_dir: Path) -> None:
    """
    Generate a plugin's vscode-mcp.json from the same `mcp:` block.

    VS Code's format differs from Claude Code's only in the top-level key —
    servers live under `servers`, not `mcpServers`. An entry declaring env
    points `command` at the same generated wrapper as .mcp.json (see
    write_mcp_json): the wrapper resolves and exports credentials itself,
    so nothing here needs VS Code's own input-prompting mechanism.
    """
    servers = {}

    for entry in plugin["mcp"]:
        name = entry["name"]
        if entry.get("env"):
            server = {
                "type": "stdio",
                "command": f"${{CLAUDE_PLUGIN_ROOT}}/bin/{name}",
                "args": [],
            }
        else:
            server = {
                "type": "stdio",
                "command": entry["command"],
                "args": entry.get("args", []),
            }
        servers[name] = server

    config = {"servers": servers}

    (plugin_dir / "vscode-mcp.json").write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )
    ok("vscode-mcp.json")


def _catalog_env(env: dict | None) -> list[dict]:
    """Build catalog.json's env list: one {name, required, description} object per variable."""
    result = []
    for var, meta in (env or {}).items():
        required, description = _normalize_env_var(meta)
        result.append({"name": var, "required": required, "description": description})
    return result


def write_catalog_json(plugin: dict, plugin_dir: Path) -> None:
    """
    Generate a plugin's catalog.json — one entry per `mcp:`/`skills:`/`deps:`
    item, naming it, its type, and its env vars as {name, required,
    description} objects (never values). Only written for a plugin
    declaring `catalog: true` in bundles.yaml.
    """
    catalog = [
        {"name": entry["name"], "type": "mcp", "env": _catalog_env(entry.get("env"))}
        for entry in plugin.get("mcp") or []
    ]
    catalog += [
        {"name": entry["name"], "type": "skill", "env": _catalog_env(entry.get("env"))}
        for entry in plugin.get("skills") or []
    ]
    catalog += [
        {
            "name": entry["command"],
            "type": "cli",
            "env": _catalog_env(entry.get("env")),
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

    plugin_dir.mkdir(parents=True, exist_ok=True)

    vendor_cfg = plugin.get("vendor")
    if vendor_cfg:
        # Vendored plugins own their entire tree (including plugin.json,
        # LICENSE, NOTICE) — skip skill/hooks/mcp/deps/catalog dispatch and
        # this repo's usual owner-stamping of plugin.json.
        fetch_vendor_plugin(vendor_cfg, plugin_dir, fetch=fetch or fetch_only)
        return

    skills_dir = plugin_dir / "skills"
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

    write_bin(plugin, plugin_dir)

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
    validate_no_duplicate_env_vars(config)
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
