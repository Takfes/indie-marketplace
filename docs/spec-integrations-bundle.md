# Spec: Secrets & MCP/CLI Management — Unified `integrations` Bundle (Design B)

> Alternative design, kept for comparison against `spec-dedicated-bundles.md`. Not filed to the
> issue tracker — local reference only.

## Problem Statement

MCP servers, CLI-driven skills that stand in for one, and skills that need an externally-sourced
credential with no CLI or server behind them at all (e.g. a plain API-key skill) are scattered
across six-plus plugins today (`python`, `research`, `web-search`, `browser`/`browser-mcp`,
`database`, `azdevops`). Each one that needs credentials re-derives the same secrets-delivery
problem described in `spec-dedicated-bundles.md` (never through Claude's context, survives
plugin upgrades, works the same across `npx`/`uvx`/plain-binary/`docker`). On top of that,
Claude Code's install granularity is per-plugin: a user cannot turn off one MCP server inside a
plugin that bundles several, so a plugin like `azdevops` is all-four-servers-or-none. As the
catalog grows — `database` is about to gain two more Docker-based servers from
`stack-database-mcp` (`mysql-mcp`, `mssql-mcp`) — every new integration re-pays this same
scattered-boilerplate cost, and the granularity problem never gets any better.

## Solution

Consolidate every MCP server, every CLI that substitutes for one (moving together with its own
skill), and every skill needing an externally-sourced credential regardless of whether a CLI or
MCP sits behind it, into one new plugin: `integrations`. Domain plugins keep only their own
skills — no infrastructure concerns. A small, self-contained local server (stdlib only, no
third-party runtime dependency — the same shape as the `lavish-axi`-style local-review-server
pattern, just purpose-built and vendored in this plugin rather than a personally-installed tool)
serves an HTML config panel listing the full catalog grouped by tag with descriptions. The user
opts in/out per entry and enters credentials directly in the browser; the browser posts straight
to that local server, which writes the real secrets file, records opt-in state, and regenerates
`integrations`' own `.mcp.json` to contain only what's opted in — so exclusion is real omission,
not a disabled-but-present entry. Claude's only role is starting and stopping that server; the
credential values travel browser → local server and never pass through a Claude tool call at
all.

## User Stories

1. As a user, I want one plugin that owns every MCP server, CLI-as-MCP tool, and credentialed integration in the marketplace, so that I have a single place to look instead of hunting across plugins.
2. As a user, I want a visual panel listing the full catalog grouped by tag (browser, research, database, web, ...), so that I can browse what's available without reading `bundles.yaml`.
3. As a user, I want each catalog entry to show a description of what it does, so that I can decide whether I want it without already knowing the tool.
4. As a user, I want to opt in or out of each entry independently, so that a plugin bundling several servers doesn't force me to take all of them.
5. As a user who opts out of an entry, I want it to be genuinely absent from the generated `.mcp.json`, not merely disabled, so that it doesn't show up as a non-functional tool in my session.
6. As a user, I want to enter credentials for the entries I opt into through the same panel, so that enabling something and configuring it are one motion, not two separate flows.
7. As a user, I want my credential values to travel straight from my browser to a local server and never pass through a Claude tool call at all, so that the secrecy guarantee from the dedicated-bundle design isn't weakened by centralizing — if anything, this route never even hands Claude a blind script invocation to make.
8. As a user, I want saving in the panel to write the real secrets file and regenerate `.mcp.json` immediately, so that my choices take effect without a separate apply step afterward.
9. As a user, I want the local server to exit after a successful save rather than linger as a background process, so that nothing keeps listening on my machine once I'm done configuring.
10. As a user, I want my opt-in selections stored somewhere version-independent, so that updating the `integrations` plugin doesn't silently reset which servers I'd enabled.
11. As a user, I want to be able to re-run the panel after a plugin update to restore or change my selections, so that an update is a deliberate re-check, not a silent reset with no recovery path.
12. As a maintainer, I want `bundles.yaml` to carry tag/group and description metadata per catalog entry, so that the panel has something to render without a second, hand-maintained source of truth.
13. As a maintainer, I want credential variable names to drop the old per-plugin-group prefix in favor of `<toolname>_<CREDENTIAL_TYPE>` (e.g. `PGQUERY_PASSWORD`, `ZOTERO_LIBRARY_ID`), kept in `UPPER_SNAKE_CASE`, so that names stay meaningful now that everything lives under one plugin.
14. As a maintainer, I want `browser`, `browser-mcp`, and `web-search` deleted outright once their entire contents move to `integrations`, so that the marketplace listing doesn't carry empty shell plugins.
15. As a maintainer, I want `python`, `research`, `database`, and `azdevops` to keep only their domain skills after their MCP/CLI entries move out, so that those plugins become pure skill bundles with no infrastructure concerns.
16. As a user of a domain skill that depends on an `integrations` catalog entry (e.g. a `python` skill wanting `context7`), I want to be told which `integrations` entry to enable, so that the cross-plugin dependency this design introduces doesn't show up as a silent failure.
17. As a maintainer, I want a `SessionStart` hook and secrets-status skill scoped to `integrations`' own catalog, so that the same nudge/status/reset behavior from the dedicated-bundle design still exists, just against one catalog instead of many.
18. As a maintainer, I want that skill to be just as unconditionally forbidden from running the apply step on the user's behalf as the dedicated-bundle design's skill was forbidden from running `configure-secrets.sh`, so that centralizing doesn't quietly drop that guarantee.
19. As a maintainer classifying `firecrawl`, `yt-dlp`, `playwright-cli` + `playwright-test-agents`, and `azure-devops-cli` as "CLI instead of MCP," I want their skills to move together with them into `integrations`, so that a CLI and the skill teaching it don't end up split across two plugins.
20. As a maintainer, I want `last30days` to move into `integrations` too, even though it has neither a CLI nor an MCP server, so that any skill needing the same credential-panel treatment lives in the one place that provides it.
21. As a maintainer adding `mysql-mcp` and `mssql-mcp` from `stack-database-mcp`, I want them to land directly in `integrations`' catalog (not in `database`, which loses its MCP entries in this design), following the same Docker + secrets pattern `pgquery` already established.
22. As a user on a machine without `lavish-axi` or any similar personally-installed tooling, I want the config panel to work anyway, so that this isn't accidentally personal-machine-only despite being shipped in a public marketplace — the vendored server must be stdlib-only, not a dependency on any tool that only exists on the maintainer's machine.
23. As a user, I want the local server to bind only to `127.0.0.1`, so that my credentials are never reachable from anything else on my network while the panel is open.
24. As a maintainer, I want CLI installation itself (running `npm install -g @playwright/cli`, etc. on the user's behalf) explicitly deferred to a second wave, so that this spec's scope stays to cataloging, opt-in, and secrets — not an installer.
25. As a maintainer, I want a boolean-only, dual-mode check script (quiet/structured for the hook, human-readable for direct use) behind both the `SessionStart` nudge and the status skill, so that "is this configured" never requires reading or printing a value to answer.

## Implementation Decisions

- **New plugin `integrations`** (working name during design was `mcps-n-clis`) aggregates every current `mcp:` entry (`context7`, `zotero`, `notebooklm`, `exa`, `pgquery`, `dbtools`, `azcloud`, `azdevops`, `azaks`, `azkusto`, plus incoming `mysql-mcp`/`mssql-mcp`), every CLI-as-MCP skill+runtime (`firecrawl`, `yt-dlp`, `playwright-cli` + `playwright-test-agents`, `azure-devops-cli`, `gh` [GitHub CLI]), and every credential-only skill with no CLI/MCP behind it (`last30days`).
- **Deleted plugins**: `browser`, `browser-mcp`, `web-search` — each fully emptied by the moves above.
- **Reduced plugins** (domain skills only, infra removed): `python` (loses `context7`, keeps 6 skills), `research` (loses `zotero`/`notebooklm`, keeps `teach`), `database` (loses `pgquery`/`dbtools`/incoming `mysql-mcp`/`mssql-mcp`, keeps 4 SQL-domain skills), `azdevops` (loses 4 MCP entries + `azure-devops-cli`, keeps 5 skills).
- **`bundles.yaml` schema addition**: `integrations`' catalog entries (both `mcp:` and its CLI-bundled `skills:`) gain `tags`/`group` and a human-facing `description` field, consumed by `build.py` to generate the panel's catalog data (analogous to how `deps.json` is generated today) rather than hand-maintaining a second copy.
- **One stable, version-independent state file** (outside any versioned plugin install path) — a single JSON file holding both enablement and credential values together, one entry per catalog item: `{"pgquery": {"enabled": true, "PGQUERY_PASSWORD": "..."}, "playwright": {"enabled": false}, ...}`. Design A needed a `.env`-format secrets file because scripts had to shell-`source` it; nothing in this design sources anything, so there's no reason to keep secrets and enablement in two files, or to use `.env` syntax instead of JSON. Credential keys use `<toolname>_<CREDENTIAL_TYPE>` in `UPPER_SNAKE_CASE` (e.g. `PGQUERY_PASSWORD`).
- **Config panel + local server** (replaces Design A's `configure-secrets.sh` for this plugin): a small stdlib-only local HTTP server (Python, matching `build.py`'s existing runtime assumption — no third-party dependency), started on demand by a skill/command, serves the panel's HTML and binds only to `127.0.0.1`. The browser posts saved selections and credential values directly to that server — not to Claude. On receiving a save, the server itself: upserts the one state file above, then regenerates `.mcp.json` from the shipped catalog plus current state — **baking each entry's resolved credential values directly into its own `env` block** (or, for `docker` commands, directly into its `-e`/`-v` args) rather than shipping a `${VAR}` placeholder or a shell-sourcing wrapper. An excluded entry is omitted from the regenerated file entirely, not disabled. Because regeneration already happens on every save, there is no separate runtime step that needs to "load" a value at launch time — the value is already sitting in `.mcp.json` by the time Claude Code starts the server, for every runtime (`npx`/`uvx`/plain binary/`docker`) alike. The server responds to the browser with a plain success page and then exits — it does not linger as a background process. Claude's only involvement is starting the server (via a skill/script) and, afterward, running the boolean-only check script to report status — it never receives the POST body and never reads the state file's contents.
- **No MCP wrapper script.** Design A needed one because its `.mcp.json` was static and had to source fresh values at every launch. This design's `.mcp.json` is regenerated (with values already baked in) every time the state changes, so there is nothing left for a wrapper to do — this entire architectural piece from `docs/secrets-architecture.md` is dropped, not ported over.
- **Check script**, same discipline as Design A's `check-secrets.sh` but reading the one JSON state file instead of a `.env` file: given the `integrations` catalog, reports per-entry set/unset via a silent presence test, never printing a matched value, in two modes on one code path — quiet/structured (for the `SessionStart` hook) and human-readable report (for the status skill and direct terminal use).
- **`SessionStart` hook + secrets-status/reset skill**: same behavior as Design A's, scoped to `integrations`' single catalog instead of enumerating multiple plugins, backed by the check script above; still unconditionally forbidden from running the configure server/panel's write path itself.
- **Docker-based entries** (`pgquery`, `dbtools`, `mysql-mcp`, `mssql-mcp`) get the same baked-in treatment as any other entry — the regeneration step just emits `-e NAME=<literal value>` / `-v <literal path>` instead of a generic command's `env` block. Same one code path, different args shape, not a different sourcing mechanism.
- **`.env.example` is not generated for this plugin's functional path.** The panel gets variable names from the catalog JSON (already needed for rendering); a separate `.env.example` would have no reader and would just be a second, driftable copy of the same names.
- **Cross-plugin dependency acknowledgment**: a domain skill that needs a specific `integrations` entry (e.g. `python`'s skills wanting `context7`) states that dependency in its own `SKILL.md` or is covered by the `SessionStart` nudge, since installing the domain plugin no longer guarantees the integration it wants is installed and enabled too.

## Testing Decisions

- Check script: same terminal-level tests as Design A's `check-secrets.sh` (no value ever printed, correct set/unset detection, first-run behavior, idempotent re-run) — same underlying discipline, now against one catalog.
- Panel rendering: manually verify the panel displays the full catalog correctly grouped/tagged from `build.py`-generated metadata, with no entry missing or miscategorized.
- Exclusion is real: manually uncheck an entry, save, confirm the regenerated `.mcp.json` has no trace of that entry (not a disabled/no-op wrapper) — verified by diffing the regenerated file, not by inspecting behavior at runtime.
- Upgrade survival: simulate a version bump (regenerate against a new fake version path) and confirm previously-saved enablement state reapplies without re-opening the panel.
- Server lifecycle: confirm the local server exits after a successful save, binds only to `127.0.0.1` (not reachable from another machine on the network), and that inspecting Claude's own tool-call transcript for the session shows no credential value anywhere in it.
- Skill refusal: same manual "just run it for me" check as Design A, confirming the status skill declines to start the server and enter values on the user's behalf.

## Out of Scope

- Automated CLI installation (actually running installers on the user's behalf) — deferred to a second wave; this spec only covers cataloging, opt-in, and secrets.
- Live/instant disabling — exclusion takes effect on next session start or `/reload-plugins`, consistent with how plugin enable/disable already behaves today, not a runtime hot-reload.
- Any reliance on browser-specific APIs (e.g. the File System Access API) — the panel must work the same in any browser, not just Chromium; a plain HTML form posting to the local server is sufficient.
- Migrating database engines beyond what's already planned: `mysql-mcp`/`mssql-mcp` as prototyped in `stack-database-mcp` today.
- Any persistent/background server — the local server this design uses is ephemeral, started on demand by a skill and exiting after a successful save, not a long-running service.
- Using GitHub CLI (`gh`) for anything in this spec's own workflow — this document, like `spec-dedicated-bundles.md`, is a local-only artifact per this exercise, not filed to the issue tracker.

## Further Notes

With the local-server panel, this design's secrecy guarantee is now on par with
`spec-dedicated-bundles.md`'s: Claude starts and stops the server but never receives the POST
body or reads the secrets file, the same way Design A's human ran `configure-secrets.sh`
directly in a terminal Claude never touched. The one tradeoff that remains is the cross-plugin
dependency this design introduces that didn't exist before (a domain skill's usefulness now
depends on a sibling plugin's opt-in state). In exchange, it's the only one of the two designs
that actually solves per-server exclusion, and it collapses the "same boilerplate re-derived per
plugin" maintenance cost that motivated this rework in the first place — while netting *fewer*
total plugins (three deleted, one added), and, per this revision, matching Design A's secrecy
guarantee rather than trading it away for centralization.

A later review against `docs/secrets-architecture.md` found three further simplifications
specific to this design that don't apply to Design A: one combined JSON state file instead of
a `.env`-format secrets file plus a separate enablement file; no MCP wrapper script at all,
since regeneration already bakes resolved values into `.mcp.json` on every save instead of
sourcing them fresh at every launch; and no generated `.env.example`, since the catalog JSON
already serves as the single source of truth for variable names. All three are consequences of
the same fact — this design has exactly one write path (the local server) for both secrets and
enablement, where Design A had two independent ones (a script that wrote secrets at any time,
and a wrapper that read them at every launch).
