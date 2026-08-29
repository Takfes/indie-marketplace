# CLI installation architecture (plan)

Status: proposed — no code shipped yet. This is the spec for the work tracked
in the linked issue, written the way [`docs/secrets-architecture.md`](secrets-architecture.md)
documents the shipped design it mirrors.

## Problem Statement

Plugins in this marketplace declare two kinds of external requirement: MCP
servers (`mcp:`) and skills (`skills:`) that need **credentials**, and a
`deps:` block for CLI tools a skill invokes **directly** (no MCP server in
front of them, e.g. `playwright-cli`). Credentials already have a full,
shipped, UX-friendly lifecycle: `~/.indie-marketplace/profiles.json`, the
`secrets-manager` skill, and a `SessionStart` hook
(`plugins/essentials/scripts/secrets-startup-check.py`) that quietly nudges
about anything partially configured.

CLI *binaries* have no equivalent. Today:

- `build.py`'s `validate_deps()` only checks that a `deps:` entry in
  `bundles.yaml` has a `command` field — it never checks whether that
  command actually exists on any machine.
- Each plugin's `deps.json` carries `command`/`install`/`manual` for its
  `deps:` entries, and `catalog.json` (opt-in via `catalog: true`) carries a
  `type: "cli"` entry with `command` + `env` for the same entries — but
  nothing ever reads either file against a real `PATH` at install time,
  session start, or on demand.
- **`mcp:` entries have their own `command` too** (`docker`, `npx`, `uvx`,
  `python`, …), and that command is never captured as a dependency
  anywhere. `docker` is the sharpest example: the `database` plugin's
  `pgquery`, `dbtools`, `mysql-mcp`, and `mssql-mcp` entries all hard-require
  a working `docker` on `PATH` (and a running daemon), yet `docker` appears
  in zero `catalog.json`/`deps.json` file in this repo. A user who installs
  `database` without Docker gets a bare "command not found" or a hung MCP
  server the first time Claude tries to call one of those tools — no
  upfront signal, no install hint.

The goal is a mechanism as good as the secrets one: tell the user what's
missing and how to fix it, without ever installing anything on their behalf.

## Solution

Mirror the secrets design's two surfaces, reusing its existing plumbing
wherever the shape matches:

1. **Passive nudge.** A new `SessionStart` hook script, sibling to
   `secrets-startup-check.py`, that once per session: discovers installed +
   enabled plugins the same way the secrets hook already does (see
   *Implementation Decisions*), reads each one's `catalog.json`, checks
   every `type: "cli"` entry's `command` against `PATH`, and — only if at
   least one required CLI is missing — emits one short, name-only nudge
   (no values, nothing to read here has a value in the first place). Silent
   when everything declared is present.
2. **On-demand check.** A `doctor` subcommand alongside the existing
   `status.py doctor` in `secrets-manager` (or a new sibling script in the
   same skill) that a user can ask for directly — *"what CLIs am I
   missing"* — and get a full per-plugin, per-tool present/missing report,
   with the `install` suggestion or `manual` link from `deps.json` attached
   to each missing one.

Neither surface ever runs an `install` command itself. `bundles.yaml`'s own
header is explicit that `install:` is "shown as a suggestion only — nothing
here is ever run automatically," and this design keeps that contract:
reporting and installing stay two different, separately-confirmed actions.

## User Stories

1. As a user installing the `database` plugin without Docker installed, I
   want a session-start nudge naming `docker` as missing before I hit a
   confusing runtime failure inside `pgquery`/`mysql-mcp`/`mssql-mcp`, so
   that I know to install it before I try to use those tools.
2. As a user who already has every CLI a plugin needs, I want complete
   silence from this mechanism, so that it never becomes noise I start
   ignoring.
3. As a user missing a CLI, I want the nudge to name the plugin and the
   tool, not just print a bare command name, so I know which plugin to
   blame/investigate.
4. As a user, I want to ask "what CLIs am I missing" at any time (not just
   at session start) and get a full report across every installed, enabled
   plugin, so I can batch my setup instead of discovering gaps one session
   at a time.
5. As a user looking at a missing-CLI report, I want the exact suggested
   install command (or a manual-install link when there isn't one) shown
   next to each missing tool, so I don't have to go find it myself.
6. As a user, I never want this mechanism to run an install command without
   me explicitly asking it to, so a stray nudge can never modify my system.
7. As a plugin maintainer adding a new `mcp:` entry that shells out to a
   CLI (e.g. another `docker run` wrapper), I want that command to be
   automatically visible to this mechanism without a separate, easy-to-forget
   `deps:` entry duplicating it, so coverage doesn't silently rot as
   `bundles.yaml` grows.
8. As a plugin maintainer, I want the build to fail loudly if I declare
   `deps:` on a plugin that doesn't also set `catalog: true`, so I can't
   ship a dependency that this mechanism can't see.
9. As a user on a marketplace-agnostic installed-plugin set (not just this
   repo's plugins), I want the check to work off any plugin's `catalog.json`
   in the same shape, so a plugin from a different marketplace that follows
   the same convention benefits too — matching why `catalog.json`/`deps.json`
   are plain JSON in the first place ("so it can be read without a YAML
   parser — for plugins from any marketplace, not just this one").

## Implementation Decisions

- **Discovery: reuse, don't reinvent.** `secrets-startup-check.py` already
  solves "which plugins are installed and enabled, and where do their
  `catalog.json` files live" via `_installed_plugin_paths()`: cross-reference
  `~/.claude/plugins/installed_plugins.json` (schema `version: 2`) against
  `enabledPlugins` in `~/.claude/settings.json`, keyed by `installPath`. The
  new hook should use the identical logic (copy the helper, same
  self-contained-script rationale the secrets hook documents in its own
  docstring — it lives in `plugins/essentials/scripts/`, which `build.py`
  never regenerates, so it isn't shared across a plugin boundary either).
- **Presence check.** `shutil.which(command)` against the current `PATH`.
  Binary-on-`PATH` only — no version pinning, no "is the Docker *daemon*
  running" check (Compose/daemon liveness is a different, heavier check;
  see Out of Scope).
- **Extend `catalog.json`'s `type: "cli"` coverage to `mcp:` commands.**
  Today `write_catalog_json()` in `build.py` only emits `type: "cli"` for
  `deps:` entries. Add one `type: "cli"` entry per **unique** `command`
  value found across a plugin's `mcp:` entries too (dedup — `pgquery`,
  `dbtools`, `mysql-mcp`, and `mssql-mcp` all say `docker`; that's one
  entry, not four). This directly closes the `docker` gap described above.
- **Install hints for `mcp:`-derived entries.** `deps:` entries carry their
  own `install`/`manual` in `bundles.yaml`; `mcp:` entries don't and
  shouldn't have to duplicate hints for widely-shared runtimes across every
  entry that happens to shell out to them. Maintain a small built-in
  fallback table in `build.py` (or in the doctor script) for the handful of
  ubiquitous ones — `docker`, `npx`, `uvx` — used only when no `deps:` entry
  for that same `command` already supplied one. Entry-level `install:` on a
  `deps:` block always wins.
- **Enforce the `deps:` ⟹ `catalog: true` invariant.** Every plugin that
  declares `deps:` today also happens to set `catalog: true` (`essentials`,
  `browser`, `web-search`, `azdevops`) but nothing enforces it. Add a check
  next to the existing `validate_deps()` that fails the build if a plugin
  has `deps:` but not `catalog: true` — a `deps:` entry this mechanism can't
  see is worse than no mechanism.
- **No new `bundles.yaml` schema.** `command`/`install`/`manual`/`env` on
  `deps:` already carry everything needed; the only generation-side change
  is broadening what `write_catalog_json()` pulls from `mcp:` entries.
- **Naming.** Keep the existing `doctor` vocabulary
  (`secrets-manager/status.py doctor`) rather than inventing a new term —
  either add a `deps.py doctor`-style sibling script in `secrets-manager`,
  or a small new script in the same skill directory that the skill's
  `SKILL.md` exposes alongside the existing secrets commands.

## Testing Decisions

- Mirror `tests/test_secrets_startup_hook.py`'s pattern exactly: spawn the
  new hook script as a subprocess with a fake `$HOME`/`installed_plugins.json`
  /`catalog.json` fixture tree and a fake `PATH` directory containing only
  some of the required binaries; assert on the hook's JSON stdout.
  - Missing required CLI → nudge naming plugin + tool.
  - All present → empty output, exit 0.
  - Malformed `catalog.json` for one plugin → that plugin is skipped, every
    other plugin's nudge still fires (same resilience contract the secrets
    hook already has and already tests).
- `build.py` test: a plugin with `deps:` and `catalog: false` fails the
  build with a clear error (new test alongside existing `validate_deps`
  coverage).
- `build.py` test: `write_catalog_json()` emits one deduped `type: "cli"`
  entry per unique `mcp:` command, on a plugin with multiple `mcp:` entries
  sharing a command (the exact `database`/`docker` shape).
- Doctor report: test only external behavior (the printed/returned report
  for a given fixture catalog + fake `PATH`), not internal helper functions
  — same bar `secrets-manager`'s own tests already hold to.

## Out of Scope

- Actually running any install command — reporting only, exactly like the
  existing `install:` field's "suggestion only" contract.
- Version pinning or minimum-version checks for any CLI.
- Docker *daemon* liveness (`docker info` succeeding) — binary presence
  only. A `docker` binary on `PATH` with a stopped daemon is a separate,
  later problem this doesn't claim to catch.
- A GUI/browser surface like the secrets manager's `index.html` — the
  doctor report is text-only, matching `status.py doctor`'s existing shape.
- Auto-migrating today's undeclared `docker` requirement retroactively into
  every existing plugin's `deps.json` — that falls out naturally once
  `write_catalog_json()` is extended to read `mcp:` commands; no manual
  `bundles.yaml` edits needed per plugin.
- The two open issues to actually build and locally tag the
  `mssql-mcp`/`mysql-mcp` Docker images — related (both plugins would start
  surfacing `docker` as a tracked dependency once this ships) but tracked
  separately.

## Further Notes

- This doc deliberately doesn't propose a new on-disk store the way
  `profiles.json` exists for secrets — CLI presence has no state to persist
  between runs (a binary is either on `PATH` right now or it isn't), so
  there's no analogue to `profiles.json`/`active` here. The hook and the
  doctor command both check live, every time.
- Once `docker` is a tracked dependency, the two Docker-image issues'
  `docker build -t indie-marketplace-{mysql,mssql}-mcp:local …` commands
  become a natural thing for the doctor report to *mention* (not run) when
  `docker` is present but those specific local tags aren't — worth
  reconsidering as a fast-follow once both that tagging convention and this
  mechanism exist, not part of this spec.
