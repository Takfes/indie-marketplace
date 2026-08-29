# CLI installation architecture (spec)

Status: agreed spec — no code shipped yet. Every claim below was checked
against the source on 2026-08-29 and the open either/or choices the first
draft carried are now decided (one deliberate exception, marked
**Captain decision** in *Implementation Decisions*). This is the spec for a
follow-up implementation issue, written the way
[`docs/secrets-architecture.md`](secrets-architecture.md) documents the
shipped design it mirrors.

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
  `deps:` entries. `catalog.json` (opt-in via `catalog: true`) carries a
  `type: "cli"` entry for the same entries, but only in the generic
  `{name, type, env}` shape every catalog entry uses — the command lands in
  `name`, and **no install hint travels with it at all**. So the one file a
  consumer already reads per plugin cannot answer "what do I run to fix
  this", and nothing ever reads either file against a real `PATH` at
  install time, session start, or on demand.
- **`mcp:` entries have their own `command` too**, and that command is
  never captured as a dependency anywhere. Today's actual values are
  `docker` (×4), `npx` (×4), `env` (×2, an argv prefix hiding the real
  command behind it), `notebooklm-mcp`, and `${AZAKS_BIN}` (a credential
  placeholder, not a binary name) — a messier set than a naive "one entry
  per `mcp:` command" rule can consume, see *Implementation Decisions*.
  `docker` is the sharpest example: the `database` plugin's `pgquery`,
  `dbtools`, `mysql-mcp`, and `mssql-mcp` entries all hard-require a
  working `docker` on `PATH` (and a running daemon), yet `docker` appears
  as a dependency in zero `catalog.json`/`deps.json` file in this repo. A
  user who installs `database` without Docker gets a bare "command not
  found" or a hung MCP server the first time Claude tries to call one of
  those tools — no upfront signal, no install hint.

The goal is a mechanism as good as the secrets one: tell the user what's
missing and how to fix it, without ever installing anything on their behalf.

## Solution

Mirror the secrets design's two surfaces, reusing its existing plumbing
wherever the shape matches:

1. **Passive nudge.** A new `SessionStart` hook script, sibling to
   `secrets-startup-check.py`, that once per session: discovers installed +
   enabled plugins the same way the secrets hook already does (see
   *Implementation Decisions*), reads each one's `catalog.json`, resolves
   every `type: "cli"` entry's `command` against `PATH` (a two-stage
   resolution — see *Presence check*), and — only if at least one required
   CLI is genuinely missing — emits one short, name-only nudge (no values,
   nothing to read here has a value in the first place). Silent when
   everything declared is present, and silent when it cannot tell.
2. **On-demand check.** A `deps.py doctor` sibling script in the
   `secrets-manager` skill directory that a user can ask for directly —
   *"what CLIs am I missing"* — and get a full per-plugin, per-tool
   present/missing report, with the `install` suggestion or `manual` link
   attached to each missing one.

Both surfaces read one file per plugin: `catalog.json`. To make that
possible the `type: "cli"` entry gains the fields it is missing today
(see *Implementation Decisions*); `deps.json` keeps its current meaning —
a verbatim copy of the `deps:` block — unchanged.

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
8. As a plugin maintainer, I want the build to fail loudly if I declare a
   `deps:` or `mcp:` block on a plugin that doesn't also set
   `catalog: true`, so I can't ship a dependency that this mechanism can't
   see.
9. As a user on a marketplace-agnostic installed-plugin set (not just this
   repo's plugins), I want the check to work off any plugin's `catalog.json`
   in the same shape, so a plugin from a different marketplace that follows
   the same convention benefits too — matching why `catalog.json`/`deps.json`
   are plain JSON in the first place ("so it can be read without a YAML
   parser — for plugins from any marketplace, not just this one").
10. As a user whose tools live on a `PATH` their shell builds (Homebrew on
    Apple Silicon, `~/.local/bin`, a version manager's shims), I want the
    check to look where my shell looks before it calls anything missing, so
    that story 2's silence survives being run from a hook rather than from
    my terminal.

## Implementation Decisions

### Discovery

- **The hook copies; the doctor imports.** `secrets-startup-check.py`
  already solves "which plugins are installed and enabled, and where do
  their `catalog.json` files live" via `_installed_plugin_paths()`:
  cross-reference `<CLAUDE_CONFIG_DIR|~/.claude>/plugins/installed_plugins.json`
  (schema `version: 2`) against `enabledPlugins` in that directory's
  `settings.json`, resolve a plugin with several install records to the one
  with the newest `lastUpdated`, strip the `@<marketplace>` suffix from the
  key, and key the result by `installPath`. The new **hook** should use the
  identical logic (copy the helper, same self-contained-script rationale
  the secrets hook documents in its own docstring — it lives in
  `plugins/essentials/scripts/`, which `build.py` never regenerates, so it
  isn't shared across a plugin boundary either).
  The **doctor** must *not* copy it. That same helper already exists a
  second time in `skills/secrets-manager/server.py`, together with
  `build_catalog()`, which returns `[{plugin, name, type, env, …}]` across
  every installed, enabled plugin — exactly the doctor's input. `status.py`
  already imports `server` from its own directory for precisely this
  reason; `deps.py` does the same and adds zero new discovery code. A third
  copy is not acceptable.

### Presence check

- **Two-stage `PATH` resolution, silent on uncertainty.** `shutil.which()`
  against the hook's own `PATH` is the fast path and the *only* stage in
  the common, everything-present case. It is not sufficient on its own: a
  hook process inherits Claude Code's `PATH`, which is the user's
  interactive shell `PATH` only when Claude Code was launched from that
  shell. Launched from a GUI or an IDE on macOS it is the bare launchd
  `PATH`, and `/etc/paths` does not include `/opt/homebrew/bin` —
  `path_helper` runs from `/etc/profile`, i.e. from a login shell a hook
  never enters. Under that `PATH` every single CLI this repo declares
  resolves to nothing, which would turn story 1's nudge into a permanent
  false alarm and destroy story 2.
  So: for any command `shutil.which()` fails to find, run **one** batched
  probe in a non-interactive login shell — `$SHELL -lc` (falling back to
  `/bin/sh -lc`), one invocation for all outstanding commands, with a hard
  2-second `subprocess` timeout inside the hook's own 5-second budget. Use
  `-lc`, never `-lic`: `-lc` sources the profile that sets `PATH` and
  measures in tens of milliseconds, while `-lic` additionally sources
  `.zshrc` (oh-my-zsh and friends) and measured 4.5s on the author's own
  machine — over budget on its own.
  A command still unresolved after both stages, or a probe that errors or
  times out, is treated as **not proven missing**: the probe failing is
  never itself a reason to nudge. `-lc` still cannot see a `PATH` entry
  added only by `.zshrc`, so this rule is what keeps the residual
  false-positive rate at zero rather than merely low.
- **Ignore a plugin's own `bin/`.** Claude Code puts every installed
  plugin's `bin/` directory on `PATH`. `build.py`'s `write_bin()` writes a
  credential-bearing `deps:` entry's scoped launcher at
  `bin/<entry.command>` — the launcher is named *exactly* the command it
  wraps. `shutil.which("playwright-cli")` would therefore find the launcher
  and report the tool present even when the real binary is absent. Both
  surfaces must reject any `which` hit whose resolved path lies under one
  of the `installPath`s discovery already collected. (No `deps:` entry
  declares `env:` today, so no such launcher exists yet — this is a latent
  trap, not a current bug, and it costs three lines to disarm now.)
- Binary-on-`PATH` only — no version pinning, no "is the Docker *daemon*
  running" check (Compose/daemon liveness is a different, heavier check;
  see Out of Scope).
- **Opt-out.** `INDIE_MARKETPLACE_SKIP_CLI_CHECK=1` in the environment makes
  the hook exit 0 silently. Story 2 is the whole point of this mechanism;
  a user who has decided a particular gap is permanent needs an exit that
  isn't "uninstall the plugin", and the doctor stays available regardless.

### Which `mcp:` commands become `type: "cli"` entries

Extend `write_catalog_json()` in `build.py` — today it emits `type: "cli"`
only for `deps:` entries — to also emit one entry per **unique** normalized
command found across a plugin's `mcp:` entries (dedup: `pgquery`,
`dbtools`, `mysql-mcp`, and `mssql-mcp` all say `docker`; that's one entry,
not four). This closes the `docker` gap described above. The normalization
rule, in order:

1. **No `command` key → skip.** No such entry exists today (`write_mcp_json`
   would raise on one), but a future remote/SSE server shape has no local
   binary to check and must not crash the build.
2. **`command: env` → unwrap.** `env KUSTO_AUTH_METHOD=… npx -y kusto-mcp`
   depends on `npx`, not on `env`; `env` is coreutils and always present,
   so emitting it is noise *and* hides the real dependency. `build.py`
   already has this exact unwrapping in `_wrapper_body()` — skip the
   leading `NAME=VALUE` args and take the first non-assignment arg as the
   command. Factor that out into a shared helper rather than writing it
   twice; it already errors on an `env` with no real command after its
   prefix, and that error should keep firing. Today this recovers `npx`
   (`azdevops/azkusto`) and `zotero-mcp` (`research/zotero`).
3. **A command containing a `${VAR}` placeholder → skip.**
   `azdevops/azaks` declares `command: ${AZAKS_BIN}`, a user-supplied
   absolute path resolved from the credential store at launch. There is no
   binary name to look for; `shutil.which("${AZAKS_BIN}")` fails forever.
   Whether `AZAKS_BIN` is set is already the *secrets* mechanism's job, and
   it already nudges about it — this one must stay out of the way.
4. **An absolute or relative path → keep as-is.** `shutil.which()` handles
   a path argument correctly (it checks that specific file for
   executability rather than searching `PATH`), so no special case is
   needed beyond using the basename for display.
5. **Everything else → a bare binary name, emitted.** That includes
   ubiquitous runtimes: `npx` is emitted, deliberately. Excluding "obvious"
   runtimes would reintroduce exactly the `docker` gap one language over —
   `npx` is required at session start by five MCP servers across three
   plugins (four declare it directly, `azdevops/azkusto` reaches it through
   rule 2), and it is the second most likely tool to be absent after
   `docker`. Noise is controlled by the eager/lazy ranking below and by
   cross-plugin dedup in the report, not by a hardcoded ignore list.

### `catalog.json`'s `type: "cli"` entry shape

The generic `{name, type, env}` shape cannot carry an install hint, and
story 9 promises a foreign plugin benefits from `catalog.json` alone. So
`type: "cli"` entries — and only those — gain three fields:

```json
{
  "name": "docker",
  "type": "cli",
  "command": "docker",
  "install": "brew install --cask docker",
  "manual": "https://docs.docker.com/get-docker/",
  "source": "mcp",
  "required_by": ["pgquery", "dbtools", "mysql-mcp", "mssql-mcp"],
  "env": []
}
```

- `name` stays the command for backward compatibility with today's files
  and with `catalog_var_names()`; `command` is the field both surfaces
  read, so the doc's own description of the check finally matches reality.
- `install`/`manual` travel *in* `catalog.json`, so the hook and the doctor
  each read one file, and a foreign plugin's hints travel with it.
- `source` is `"deps"` or `"mcp"`; `required_by` names the `mcp:` entries
  that produced it (empty for a `deps:`-derived entry). Together these give
  story 3 its "which plugin, which tool" wording and drive the ranking
  below.
- `deps.json` is unchanged — `bundles.yaml`'s header defines it as a
  verbatim copy of the `deps:` block, and nothing here needs it to become
  something else. In particular `database` gains no `deps.json`; its
  `docker` requirement lives in `catalog.json` where both consumers already
  look.

Both `bundles.yaml`'s header comment for `plugin.catalog` and `build.py`'s
module docstring describe catalog.json as "one `{name, type, env}` object
per mcp:/skills:/deps: entry". Both must be updated in the same change —
they are the contract this design leans on.

### Install hints for `mcp:`-derived entries

`deps:` entries carry their own `install`/`manual` in `bundles.yaml`;
`mcp:` entries don't and shouldn't have to duplicate hints for
widely-shared runtimes across every entry that happens to shell out to
them. Keep a small built-in fallback table for the handful of ubiquitous
ones — `docker`, `npx` today — used only when no `deps:` entry for that
same `command` already supplied one. Entry-level `install:` on a `deps:`
block always wins.

**Decision: the table lives in `build.py`, not in the doctor script.** Two
reasons, both structural. A hint resolved at build time is baked into the
shipped `catalog.json`, so it reaches every consumer — the doctor, the
hook's nudge, another marketplace's tooling, and a human reading the file
— from one place; a hint resolved in the doctor would need a second copy in
the hook to render a hint in the nudge at all, and would leave story 9's
foreign plugin with nothing. And a build-time table makes a hint change
show up as a reviewable diff in the generated files, the same way every
other `bundles.yaml`-derived fact does. The cost — a hint change requires a
rebuild — is the cost this repo already pays for every generated file.

A command with neither a `deps:`-supplied hint nor a table entry
(`notebooklm-mcp`, `zotero-mcp` today) still surfaces, marked as having no
declared install hint. Adding a `deps:` entry for that command is the
supported way to give it one; the "`deps:` wins" rule already makes that
work with no further mechanism.

### Build-time invariants

- **`deps:` or `mcp:` ⟹ `catalog: true`.** Every plugin declaring `deps:`
  today does set `catalog: true` (`essentials`, `browser`, `web-search`,
  `azdevops` — checked across all fifteen plugins, no others declare
  `deps:`), and so does every plugin declaring `mcp:` (`pythonista`,
  `database`, `azdevops`, `research`, `web-search`). Nothing enforces
  either. Add a check that fails the build when a plugin declares `deps:`
  or `mcp:` without `catalog: true` — a dependency this mechanism can't see
  is worse than no mechanism.
- **It must be a config-level validator, not a `validate_deps()` sibling.**
  `validate_deps()` runs inside `build_plugin()`, and only under
  `if plugin.get("deps")` — so `./build.py --plugin other` never evaluates
  it for the offending plugin. Put the new check next to
  `validate_no_duplicate_env_vars(config)`, which `main()` calls on the
  whole config *before* the `--plugin` filter. That path is already proven
  by `test_duplicate_check_runs_on_scoped_plugin_build`.
- **No new `bundles.yaml` schema.** `command`/`install`/`manual`/`env` on
  `deps:` already carry everything needed; the generation-side changes are
  broadening what `write_catalog_json()` pulls from `mcp:` entries and
  widening the `type: "cli"` entry shape.

### Ranking, and what the nudge covers

A `type: "cli"` entry's `source` says *when* it is required, and the two
cases are genuinely different:

- `source: "mcp"` — **required eagerly.** Claude Code launches every
  enabled plugin's MCP servers at session start whether or not the user
  ever calls a tool on them. A missing `docker` is not "required by
  something you may never invoke"; it is a connection failure the user sees
  on every single session start. This is the *stronger* requirement, not
  the weaker one, and the report should say so.
- `source: "deps"` — **required lazily**, on first use of the skill that
  shells out to it. Nothing breaks until the user invokes that skill.

The doctor reports both, `mcp`-derived first, deduped by command across
plugins (`npx` is one line naming three plugins, not three lines).

> **Captain decision — does the *nudge* cover lazily-required
> (`source: "deps"`) CLIs, or only eagerly-required ones?**
> This is a noise judgment, not a technical one, so it is left open
> deliberately. Concretely today: on a machine with `web-search` installed,
> `firecrawl` is missing and `yt-dlp` is present, so option (a) adds one
> permanent line to every session until `firecrawl` is installed or the
> opt-out is set.
>
> (a) Nudge on both. Maximum coverage; a rarely-used plugin's missing CLI
>     nags forever.
> (b) Nudge only on `source: "mcp"`; the doctor still covers both. Silence
>     is preserved for the lazy case, which is exactly the case that fails
>     loudly and locally at first use anyway.
> (c) Nudge on both, but at most once per (plugin, command) per machine via
>     a marker file. Best UX, and the only option that introduces on-disk
>     state this design otherwise avoids entirely.
>
> Recommendation: **(b)** — it is the only option that costs nothing and
> keeps story 2 absolute, and the lazy case's own failure is already
> self-explanatory ("command not found: firecrawl") in a way an MCP server
> failing to connect at startup is not.

### Naming and the doctor's surface

Keep the existing `doctor` vocabulary (`secrets-manager/status.py doctor`)
rather than inventing a new term. **Decision: a new sibling script,
`deps.py`, with a `doctor` subcommand, in `skills/secrets-manager/`** —
not a fourth subcommand on `status.py`.

`status.py`'s module docstring opens "Value-blind status reporting for
indie-marketplace credential **profiles**", and all three of its
subcommands answer questions about the credential store; a CLI-presence
check would make that sentence false and would mix two unrelated failure
domains behind one exit code. A sibling in the same directory keeps the one
thing that actually matters — it can `import server` and reuse
`build_catalog()` and `_installed_plugin_paths()`, exactly as `status.py`
already does — while keeping the domains separate. Discoverability costs
the same either way: `SKILL.md` needs a new `## Missing CLI tools` section
and one added clause in the skill's `description` frontmatter, because as
written that description mentions only credentials and would never route
story 4's "what CLIs am I missing" to this skill at all.

Exit code follows `status.py doctor`: `0` when nothing is missing, `1`
otherwise.

### Hook registration

`plugins/essentials/hooks/hooks.json` is hand-maintained (essentials has no
`hooks:` block in `bundles.yaml`; that block is for *fetched* community
hooks). Registering the new script means adding a second entry to the
existing `SessionStart` / `matcher: "startup"` group, with its own
`timeout`. `"startup"` — not `"resume"`/`"clear"`/`"compact"` — is what
delivers "once per session", matching the secrets hook exactly. Keep the
new hook a separate script rather than folding the check into
`secrets-startup-check.py`: the two have different domains and different
failure modes, and a malformed credential store must not be able to
suppress a CLI nudge or vice versa.

## Testing Decisions

- Mirror `tests/test_secrets_startup_hook.py`'s pattern exactly: spawn the
  new hook script as a subprocess with a fake `CLAUDE_CONFIG_DIR` /
  `installed_plugins.json` / `catalog.json` fixture tree; assert on the
  hook's JSON stdout. That harness already passes an explicit
  `PATH="/usr/bin:/bin"` to the subprocess, so pointing `PATH` at a fixture
  directory holding only some of the required binaries is a one-line
  extension of an existing, working pattern.
  - Missing required CLI → nudge naming plugin + tool.
  - All present → empty output, exit 0.
  - A binary found only via the login-shell probe → silent (set `SHELL` to
    a stub script that prints the command, so the probe is deterministic
    and never touches the developer's real dotfiles).
  - Probe that errors or times out → silent, exit 0. Never a nudge.
  - A `which` hit resolving inside a fixture plugin's own `bin/` → treated
    as missing, not present.
  - `INDIE_MARKETPLACE_SKIP_CLI_CHECK=1` → silent, exit 0.
  - Malformed `catalog.json` for one plugin → that plugin is skipped, every
    other plugin's nudge still fires (same resilience contract the secrets
    hook already has and already tests).
- `build.py` tests, via `tests/test_build.py`'s synthetic-`bundles.yaml`
  harness:
  - A plugin with `deps:` (and one with `mcp:`) and no `catalog: true`
    fails the build with a clear error, **including under
    `--plugin <other>`** — the scoped-build case
    `test_duplicate_check_runs_on_scoped_plugin_build` already models.
  - `write_catalog_json()` emits one deduped `type: "cli"` entry per unique
    `mcp:` command, on a plugin with multiple `mcp:` entries sharing a
    command (the exact `database`/`docker` shape), carrying `install` from
    the fallback table and `required_by` naming all four entries.
  - Normalization: `command: env A=1 realcmd` yields `realcmd`;
    `command: ${VAR}` yields no entry; a missing `command` key yields no
    entry and no crash.
  - A `deps:` entry's own `install:` overrides the fallback table for the
    same command.
  - `validate_deps()`'s own failure path (a `deps:` entry with no
    `command`) is **not** covered today — no test in the suite exercises
    it. Add it alongside the new checks.
- Doctor report: test only external behavior (the printed report and exit
  code for a given fixture catalog + fake `PATH`), not internal helper
  functions — same bar `secrets-manager`'s own tests already hold to.
  Include the cross-plugin dedup case: one `npx` line naming three plugins.

## Out of Scope

- Actually running any install command — reporting only, exactly like the
  existing `install:` field's "suggestion only" contract.
- Version pinning or minimum-version checks for any CLI.
- Docker *daemon* liveness (`docker info` succeeding) — binary presence
  only. A `docker` binary on `PATH` with a stopped daemon is a separate,
  later problem this doesn't claim to catch, and so is a present daemon
  without the locally-tagged image an entry needs. Worth stating plainly in
  the doctor's output so "docker: present" is never misread as "the
  `database` plugin will work".
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
- **The scoped-launcher self-recursion bug this design surfaced but does not
  fix.** `_scoped_launcher_script()` emits `exec <command> "$@"` into
  `bin/<command>`, and Claude Code puts that `bin/` on `PATH`. If the real
  binary is absent, the launcher re-resolves its own name and execs itself.
  No `deps:` entry declares `env:` today so nothing triggers it; it is a
  `build.py` correctness issue, not a CLI-check issue, and belongs in its
  own issue. This spec only ensures the presence check is not *fooled* by
  those launchers.
- Remote/SSE `mcp:` entries (no local `command`). `build.py` cannot express
  them today; rule 1 above only guarantees this mechanism won't break when
  it can.

## Further Notes

- This doc deliberately doesn't propose a new on-disk store the way
  `profiles.json` exists for secrets — CLI presence has no state to persist
  between runs (a binary is either on `PATH` right now or it isn't), so
  there's no analogue to `profiles.json`/`active` here. The hook and the
  doctor command both check live, every time. The one thing that would
  introduce state is nudge option (c) in the Captain decision above; that
  is the honest cost of that option.
- Once `docker` is a tracked dependency, the two Docker-image issues'
  `docker build -t indie-marketplace-{mysql,mssql}-mcp:local …` commands
  become a natural thing for the doctor report to *mention* (not run) when
  `docker` is present but those specific local tags aren't — worth
  reconsidering as a fast-follow once both that tagging convention and this
  mechanism exist, not part of this spec.
