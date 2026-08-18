---
name: runtime-doctor
description: Check whether the runtimes your installed Claude Code plugins depend on (Node/npx, uv/uvx, Bun, Docker) are actually present on PATH, and offer to install any that are missing. Use when a plugin's MCP server fails to start, after installing a batch of plugins, or when the user asks to check, verify, or fix their toolkit setup. Never installs anything without asking first.
---

# Runtime Doctor

## Overview

Plugins declare MCP servers that shell out to a runtime — `npx` for Node-based
servers, `uvx` for Python ones, `bun`, `docker`. If that runtime isn't on PATH
the server fails silently at session start, and the plugin looks broken for no
visible reason.

This skill answers: *which runtimes do my installed plugins actually need, and
do I have them?*

Use it when:

- **A plugin isn't working** — its MCP server may be failing to launch
- **After installing plugins** — verify the new set's dependencies in one pass
- **Setting up a new machine** — find out what to install before hitting errors
- **The user asks** to "check my toolkit setup", "verify my plugins", or similar

This skill is strictly on demand. It is not wired to session start and must
never be run automatically.

## Quick Start

Report what's needed and what's missing. This never installs anything:

```bash
python3 scripts/check_runtimes.py
```

If a runtime is missing, install exactly one — only after the user has approved
the exact command:

```bash
python3 scripts/check_runtimes.py --install uv --yes
```

## How It Works

1. Runs `claude plugin list --json` — Claude Code's own record of what's
   installed. Disabled plugins are skipped, since their MCP servers don't run.
2. Reads each plugin's `mcpServers` block from that output and collects every
   declared `command` (`npx`, `uvx`, `bun`, …).
3. Checks each command against PATH.
4. Prints a per-command verdict naming which plugin and which server needs it,
   then lists the install command for anything missing — without running it.

Plugins from every marketplace are covered, not just this one; the report names
the source marketplace so it's clear where each requirement comes from.

Skills fetched from git have no runtime dependency in this sense and are
ignored — only declared MCP servers are inspected. Servers whose `command` is a
path or a `${VAR}` are skipped too: those ship with the plugin and are resolved
by Claude Code, so they aren't something the user installs.

## Workflow

Run the report first and show the user the result verbatim.

**If nothing is missing**, say so and stop. Do not install anything.

**If something is missing**, tell the user which runtime, which plugin needs it,
and the exact command that would run. Ask whether to proceed. Only after they
say yes, run the script again with `--install <runtime> --yes`.

Never chain the check and the install in a single step, and never install a
runtime the user didn't approve by name. `--yes` is your assertion that the user
already approved that exact command — without it the script refuses to install
when there's no terminal to confirm at.

After a successful install the new binary lands in a shell profile, so it won't
be on PATH in the current session — tell the user to start a new shell, then
re-run the report to confirm.

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| _(none)_ | — | Report only. Lists required runtimes and flags missing ones. Never installs. |
| `--install RUNTIME` | No | Install one runtime: `node`, `uv`, `bun`. Prompts for confirmation in a terminal; refuses without one unless `--yes` is passed. |
| `--yes` | No | Confirms the install non-interactively. Pass only once the user has approved that exact command. |

`--install` refuses unless that runtime is both **needed by an installed plugin**
and **actually missing** — it will not upgrade or re-link a toolchain that's
already working.

`docker` and `python` are reported but never installed by this script, which
points at the official instructions instead of guessing at a package manager.
`node` is only offered on macOS with Homebrew present; otherwise the report
links to the official download.

## Verification

Confirm a runtime landed after installing:

```bash
which uv && uv --version
```

Then re-run the report; the runtime should flip from `missing` to `ok`.

## Resources

**Script:** `scripts/check_runtimes.py`
- Stdlib-only Python 3, deliberately not a uv script — uv is one of the
  runtimes it detects the absence of, so it cannot depend on it
- Executable without reading into context (can be called directly)
