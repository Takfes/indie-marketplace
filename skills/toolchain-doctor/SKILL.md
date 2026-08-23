---
name: toolchain-doctor
description: Check whether the runtimes (Node/npx, uv/uvx, Bun, Docker) and catalog CLI dependencies your installed Claude Code plugins depend on are actually present on PATH, and offer to install any missing runtime. Use when a plugin's MCP server or a skill's CLI tool fails to start, after installing a batch of plugins, or when the user asks to check, verify, or fix their toolkit setup. Never installs anything without asking first.
---

# Toolchain Doctor

## Overview

Plugins declare MCP servers that shell out to a runtime — `npx` for Node-based
servers, `uvx` for Python ones, `bun`, `docker`. If that runtime isn't on PATH
the server fails silently at session start, and the plugin looks broken for no
visible reason.

Some plugins also drive a plain CLI tool directly from a skill, with no MCP
server behind it at all — bundles.yaml's `deps:` block is how those get
declared (see `integrations`' `gh`/`yt-dlp`/`firecrawl` entries), so they
show up in this same report instead of staying invisible to it.

This skill answers: *which runtimes and CLI tools do my installed plugins
actually need, and do I have them?*

Use it when:

- **A plugin isn't working** — its MCP server, or a skill's CLI tool, may be missing
- **After installing plugins** — verify the new set's dependencies in one pass
- **Setting up a new machine** — find out what to install before hitting errors
- **The user asks** to "check my toolkit setup", "verify my plugins", or similar

This skill is strictly on demand. It is not wired to session start and must
never be run automatically.

## Quick Start

Report what's needed and what's missing. This never installs anything:

```bash
python3 scripts/check_toolchain.py
```

If a runtime is missing, install exactly one — only after the user has approved
the exact command:

```bash
python3 scripts/check_toolchain.py --install uv --yes
```

## How It Works

1. Runs `claude plugin list --json` — Claude Code's own record of what's
   installed. Disabled plugins are skipped, since their MCP servers don't run.
2. **Runtimes:** reads each plugin's `mcpServers` block from that output and
   collects every declared `command` (`npx`, `uvx`, `bun`, …).
3. **Catalog dependencies:** reads `deps.json` from each installed plugin's own
   directory (`installPath` in the JSON above), if it has one — the file
   build.py writes from that plugin's `deps:` block in bundles.yaml. Skipped
   entirely for a plugin that never declared one.
4. Checks every collected command against PATH.
5. Prints a per-command verdict naming which plugin needs it, then lists an
   install suggestion for anything missing — without running it.

Plugins from every marketplace are covered for the runtime check, not just this
one; the report names the source marketplace so it's clear where each
requirement comes from. The catalog-dependency check works the same way for
any marketplace's plugins, as long as that plugin shipped its own deps.json —
this script has no YAML parser and never reads bundles.yaml directly.

Skills fetched from git have no runtime dependency in this sense and are
ignored — only declared MCP servers and deps.json entries are inspected.
Servers whose `command` is a path or a `${VAR}` are skipped too: those ship
with the plugin and are resolved by Claude Code, so they aren't something the
user installs.

## Workflow

Run the report first and show the user the result verbatim.

**If nothing is missing**, say so and stop. Do not install anything.

**If a runtime is missing**, tell the user which runtime, which plugin needs it,
and the exact command that would run. Ask whether to proceed. Only after they
say yes, run the script again with `--install <runtime> --yes`.

**If a catalog dependency is missing**, tell the user the command, which plugin
needs it, and the install suggestion from the report (if any) — `--install`
only ever installs runtimes, never a catalog entry, so hand the suggested
command to the user to run themselves.

Never chain the check and a runtime install in a single step, and never install
a runtime the user didn't approve by name. `--yes` is your assertion that the
user already approved that exact command — without it the script refuses to
install when there's no terminal to confirm at.

After a successful install the new binary lands in a shell profile, so it won't
be on PATH in the current session — tell the user to start a new shell, then
re-run the report to confirm.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| _(none)_ | — | Report only. Lists required runtimes and catalog dependencies and flags missing ones. Never installs. |
| `--install RUNTIME` | No | Install one runtime: `node`, `uv`, `bun`. Prompts for confirmation in a terminal; refuses without one unless `--yes` is passed. Never applies to catalog dependencies. |
| `--yes` | No | Confirms the install non-interactively. Pass only once the user has approved that exact command. |

`--install` refuses unless that runtime is both **needed by an installed plugin**
and **actually missing** — it will not upgrade or re-link a toolchain that's
already working.

`docker` and `python` are reported but never installed by this script, which
points at the official instructions instead of guessing at a package manager.
`node` is only offered on macOS with Homebrew present; otherwise the report
links to the official download. Catalog dependencies are never installed by
this script either — the report only ever shows the suggested command.

## Verification

Confirm a runtime landed after installing:

```bash
which uv && uv --version
```

Then re-run the report; the runtime should flip from `missing` to `ok`. The
same applies to a catalog dependency after the user installs it by hand.

## Resources

**Script:** `scripts/check_toolchain.py`
- Stdlib-only Python 3, deliberately not a uv script — uv is one of the
  runtimes it detects the absence of, so it cannot depend on it
- Executable without reading into context (can be called directly)
