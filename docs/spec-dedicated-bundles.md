# Spec: Secrets & MCP/CLI Management — Dedicated Per-Plugin Bundles (Design A)

> Alternative design, kept for comparison against `spec-integrations-bundle.md`. Not filed to
> the issue tracker — local reference only.

## Problem Statement

Several plugins in this marketplace ship an MCP server or a CLI-driven skill that needs a
credential — an API key, a connection string, a config file path. Today there is no reliable
way for a value the user enters once to reach the running server or CLI process:

- `.mcp.json`'s `${VAR}` substitution only resolves from whatever shell launched Claude Code —
  it does not read `.env` or any file automatically.
- A plugin's install path is versioned (`.../<plugin>/<version>/...`); anything written inside
  it is lost the next time the plugin updates.
- Docker-based servers (`pgquery`, `dbtools`) don't inherit host environment at all — they need
  values passed explicitly via `-e`/`-v`.
- Whatever mechanism solves this must never put a credential's actual value through Claude's
  own context — a user typing a password into chat, or an agent echoing a file's contents to
  "check" it, both leak the secret into the transcript.

This design keeps today's plugin grouping intact (`python`, `research`, `web-search`,
`database`, `azdevops`, `browser`/`browser-mcp`, each owning their own MCP/CLI entries) and adds
the missing secrets-delivery mechanism on top, without restructuring which plugin owns which
integration.

## Solution

Every plugin that declares `env` names on an `mcp:` entry (or a bare CLI credential) gets: a
stable, version-independent secrets file; a generated `.mcp.json` command that sources that file
before launching the real server or CLI; a boolean-only check script; an interactive configure
script that only a human runs; and a marketplace-wide `SessionStart` nudge plus a
secrets-management skill that never touches a value directly.

## User Stories

1. As a plugin author, I want a fixed, per-plugin secrets file path keyed only by plugin name, so that a plugin version upgrade never wipes a user's configured credentials.
2. As a user, I want to run one script to set up a plugin's credentials, so that I don't have to hand-edit files or guess a path.
3. As a user, I want the configure script to mask my input as I type it, so that a credential never appears in my terminal scrollback.
4. As a user re-running the configure script, I want to see which variables are already set without seeing their values, so that I can choose to keep or overwrite each one without retyping everything.
5. As a user, I want a check script that tells me which variables are missing for a given plugin, so that I know exactly what's left to do.
6. As a plugin maintainer, I want the check script's logic to run in exactly one place with two output modes (quiet/structured for a hook, human-readable for direct use), so that the two never drift apart.
7. As a user, I want the check script to never print a variable's value under any invocation, so that running it — even by accident, even by Claude on my behalf — cannot leak a credential.
8. As a user starting a real Claude Code session, I want to be told if any installed plugin is missing required secrets, so that I notice before I try to use it and get a confusing failure instead.
9. As a user, I want that startup nudge to stay silent and add no noticeable delay when everything is already configured, so that most sessions are unaffected.
10. As a user, I want the nudge to fire only on a real session start, not on `/clear` or context compaction, so that it doesn't repeat mid-conversation.
11. As a user, I want a single skill I can ask about secrets status across every installed plugin, so that I don't have to remember which plugins need what.
12. As a user, I want that skill to tell me exactly where a given plugin's secrets file lives, so that I can inspect or back it up myself if I want to.
13. As a user, I want that skill to tell me the exact command to run to configure a plugin, so that I can go do it myself in my own terminal.
14. As a user, I want that skill to refuse to run the configure command on my behalf even if I explicitly ask it to, so that the "Claude never sees a secret" guarantee can't be argued away in the moment.
15. As a user, I want that skill to be able to delete or reset a plugin's stored secrets directly, so that I can rotate a credential without hand-editing a file.
16. As a plugin author adding a new `mcp:` entry with a non-Docker command, I want `build.py` to generate a `.mcp.json` command that sources the plugin's secrets file before handing off to the real command, so that the server gets credentials without depending on the launching shell.
17. As a plugin author using `command: docker`, I want `build.py` to generate a command that passes secrets explicitly via `-e`/`-v` (as `pgquery`/`dbtools` already do today), so that the container receives values it otherwise wouldn't inherit.
18. As a plugin author renaming a repo-prefixed variable to a fixed name a container expects (e.g. `DATABASE_PGQUERY_URI` → `DATABASE_URI`), I want that rename to keep working under the new generation, so that existing Docker entries don't regress.
19. As a maintainer, I want `.env.example` generation to be unaffected by any of this, so that the documented list of what a plugin needs stays accurate without extra work.
20. As a maintainer, I want `load-env.sh` and its cross-plugin collision-detection logic removed once the new mechanism lands, so that the repo doesn't carry a dead, misleading description of how secrets reach a server.
21. As a maintainer, I want the per-plugin variable name prefix (`DATABASE_`, `AZDEVOPS_`, etc.) kept for readability even though it's no longer needed to avoid collisions, so that `.env.example` files stay human-scannable.
22. As a maintainer adding `mysql-mcp` and `mssql-mcp` (currently prototyped in `stack-database-mcp`, not yet in this repo) to the `database` plugin, I want them to follow the exact same Docker + secrets-file pattern as `pgquery`, so that the fourth and fifth Docker-based server don't need a new mechanism.
23. As a user, I want the whole thing to work identically whether a plugin's MCP command is `npx`, `uvx`, a plain binary, or `docker`, so that I don't need to know which runtime a given server happens to use.

## Implementation Decisions

- **Stable secrets file**: one file per plugin, path keyed only by plugin name (not version, not install path) — e.g. `~/.claude/indie-marketplace/secrets/<plugin>.env`.
- **Two shared scripts**, hand-maintained (not generated) and vendored where every plugin needing them can reach them:
  - `check-secrets.sh` — given a plugin, reads its `.env.example` variable names and reports set/unset per name via a silent `grep -q` test; never prints a matched line or value. Two modes on one code path: `--quiet` (emits `hookSpecificOutput` JSON, only when something's missing) and `--report [plugin]` (human-readable, all plugins or one).
  - `configure-secrets.sh` — takes a plugin name, reads its `.env.example`, prompts per variable with `read -s` (not echoed), shows current set/unset status on re-run so unchanged values don't need retyping, upserts into the secrets file, `chmod 600`s it, and calls `check-secrets.sh --report` at the end.
- **`.mcp.json` wrapper codegen** in `build.py`: for every `mcp:` entry with declared `env`, generate a command that sources the plugin's secrets file immediately before exec'ing the real command — a plain shell one-liner for non-Docker commands (preserving the real command's exit behavior and stdio, no leftover wrapper process), explicit `-e`/`-v` flags sourced from the secrets file for `command: docker`.
- **`SessionStart` hook**: enumerates installed `@indie-marketplace` plugins (`claude plugin list --json`), runs `check-secrets.sh --quiet` per plugin, surfaces a nudge into Claude's context only when something is missing — naming which plugin(s) and how many variables, never a value.
- **Secrets-management skill**: lives in `essentials` (not the domain plugins, since it's cross-cutting infrastructure, not plugin-specific know-how). Reports status for all installed plugins, locates a given plugin's secrets file, states the exact configure command, deletes/resets a plugin's file — and its own instructions explicitly and unconditionally forbid it from running the configure command itself.
- **Granularity stays at the plugin level.** There is no mechanism in this design for a user to enable a subset of a multi-server plugin's MCP entries — `azdevops`'s four servers launch together, or not at all, exactly as today. If a maintainer wants an optional subset, the only lever is splitting it into its own plugin ahead of time, as `browser`/`browser-mcp` already do.
- **Env var naming unchanged**: existing per-plugin prefix convention (`DATABASE_PGQUERY_URI`, `AZDEVOPS_AZKUSTO_CLIENT_ID`) is kept, rationale comment updated from "prevents a runtime collision" to "kept for readability."

## Testing Decisions

- `check-secrets.sh` / `configure-secrets.sh`: run directly from a terminal, no Claude session involved. Verify set/unset detection is correct, no invocation ever prints a value, first-ever run (no secrets file yet) doesn't error, re-running after partial configuration correctly shows mixed set/unset status.
- Wrapper codegen: regenerate one non-Docker plugin (e.g. `azdevops`'s `azkusto`) and one Docker plugin (`database`'s `pgquery`) with `./build.py --plugin <name>`, manually start the generated command with a populated secrets file, confirm the real process receives every declared variable. Marketplace-wide retrofit beyond these two examples is not required to close this spec.
- Hook: trigger a real session start with a plugin's secrets file emptied or renamed, confirm the nudge appears with correct plugin/count; confirm no nudge and no perceptible delay when everything is configured.
- Skill: manually ask it to "just run the setup for me" and confirm it declines and re-explains, rather than complying.

## Out of Scope

- Retrofitting every MCP-bearing plugin's `.mcp.json` in one pass — proving the mechanism on one non-Docker and one Docker example is sufficient; a marketplace-wide rollout is a separate, later effort.
- Per-server exclusion within a single plugin's `.mcp.json` — not achievable in this design; a plugin's servers are all-or-nothing.
- Automated CLI installation (actually running `npm install -g`, etc. on the user's behalf) — CLIs remain self-documented, installed by hand, exactly as today.
- Any change to which plugin owns which MCP/CLI entry — this design deliberately preserves today's grouping.

## Further Notes

This is the design originally explored and partially ticketed earlier in this project (see
`docs/secrets-architecture.md` for the fuller narrative, sequence diagram, and worked examples —
still accurate as a description of this design's mechanics even though its own ticket/issue
were later withdrawn pending this comparison). Its central limitation, carried forward
unresolved from today's setup, is that Claude Code's install granularity is per-plugin: this
design solves *credential delivery* but not *selective enablement* of one server among several
bundled in the same plugin.
