# Plugin secrets architecture

How MCP-server and CLI credentials get from "declared in `bundles.yaml`" to
"available to a running process" — without a value ever passing through a
model's own context, and without a value ever differing silently between
projects.

This document describes the design shipped across issues #66–#72 (parent
spec #65). It supersedes an earlier per-plugin, `configure-secrets.sh`-driven
design — that one never shipped; nothing below should be read as a
description of it.

## TL;DR

- All credentials live in one file, `~/.indie-marketplace/profiles.json`
  (mode `0600`), grouped into named **profiles**. `base` holds your
  defaults; any other profile (`client-a`) overrides only what differs for
  it and inherits everything else from `base`.
- A profile is selected per process, in order: `$INDIE_PROFILE` env var →
  the profile bound to the longest matching project path → the machine-wide
  `active` file → `base`.
- You edit values in a browser, never a terminal prompt. Ask the
  **secrets-manager** skill (bundled with `essentials`) to open it. Claude
  hands you a `127.0.0.1` URL and never sees a value.
- Generated wrapper scripts sit between `.mcp.json` and the real command —
  they resolve the active profile's values and export them, so `${VAR}`
  substitution and hand-exported shell variables are both gone from this
  design entirely.
- A `SessionStart` hook nudges you, once per session, about any tool that's
  *partially* configured — never about one you haven't touched.

## Get started

**Open the manager.** Ask Claude: *"open the secrets manager"* — it
launches a local server and gives you a link. Open it in a browser.

**Fill in `base`.** Screen A lists every variable every installed,
enabled plugin declares, grouped by tool, each tagged required or optional.
Values you enter here apply everywhere, for every project, unless a more
specific profile overrides them. Put your global credentials here — a
Zotero API key, an Exa key — anything that's the same regardless of which
project you're in.

**Need a value to differ per project?** Create a profile (e.g. `client-a`),
override just the variables that differ for it, and bind it to that
project's directory. Opening Claude Code inside that directory now resolves
`client-a` automatically — nothing to type.

**Working outside a bound directory, or need to override one for a single
session?** See [Launch ergonomics](#launch-ergonomics) below.

**Check what's still missing without opening a browser:** ask Claude
*"what secrets are unset"* or *"which profile applies here"* — the
secrets-manager skill answers both without ever reading a value (see
[The secrets-manager skill](#the-skill)).

## Store layout

- Root: `~/.indie-marketplace/`, mode `0700`. Overridable via
  `$INDIE_MARKETPLACE_HOME` (used by this repo's own tests; not a supported
  user-facing knob).
- `profiles.json`, mode `0600`:

  ```json
  {
    "version": 1,
    "profiles": {
      "base":     { "projects": [], "values": { "ZOTERO_API_KEY": "..." } },
      "client-a": { "projects": ["/Users/x/work/client-a"], "values": { "PGQUERY_URI": "..." } }
    }
  }
  ```

  Values sit under a nested `values` key so a variable name can never
  collide with a metadata key like `projects`. `base` always exists, can't
  be deleted or renamed, and legitimately holds no value for a variable
  that's inherently per-project — that isn't an error, it just means the
  variable is unset outside a bound profile.
- `active`, mode `0600`: one line, a profile name. Absent, or naming a
  profile that no longer exists, means "fall back to `base`" — never an
  error.
- Every write goes temp-file-then-`os.replace`, with the mode set on the
  temp file before the rename — no window where a crash mid-write leaves a
  partially-written or wrongly-permissioned file visible to a reader
  (`shared/indie_store.py`'s `_atomic_write`).

## Resolution, stated once

Every consumer of this store — the resolver copied into each plugin's
`bin/`, the web server, the status CLI, the `SessionStart` hook — implements
this exact precedence. It is not restated per-consumer below.

**Which profile:**

```
$INDIE_PROFILE
  -> the profile whose projects[] entry is the longest path-segment
     prefix of realpath($PWD)
  -> the contents of ~/.indie-marketplace/active
  -> "base"
```

The path match compares whole path *segments*, not raw string prefixes, so
a profile bound to `/work/client-a` never matches a session running in
`/work/client-ab`.

**Which value, once a profile is chosen:**

```
profiles[profile].values[NAME]
  -> profiles["base"].values[NAME]
  -> unset
```

An empty string is treated as unset at every layer — storing `""` for a
variable falls through to `base` exactly as if the key were absent. This is
intentional: it's what a wrapper's real runtime resolution does, so the UI
and status tooling report the same thing a launched process would actually
see. (The UI's Save action separately refuses to *write* a functionally
inert empty-string override in the first place — see
[The web UI](#the-web-ui).)

## `base` versus `active` — not the same word

Both were called "default" at points during design; they are two different
files and must stay two different words:

- **`base`** is a *profile* — a place values live, and the fallback every
  other profile inherits from.
- **`active`** is a *file* naming which profile a process should resolve to
  when nothing more specific says otherwise (no `$INDIE_PROFILE`, no bound
  project path match).

Setting the active profile to `client-a` does not move or copy any values —
it only changes what an unbound session resolves to.

## Wrappers and scoped launchers

**Why they exist at all.** `${VAR}` in `.mcp.json` expands from the
environment of the process that launched Claude Code — it has no way to
read a value out of `profiles.json`. Nothing in `.mcp.json` or
`vscode-mcp.json` can resolve a stored credential by itself; something has
to read the store and hand the value to the launched process. That
something is a generated wrapper.

**Which entries get one.** Any `mcp:` entry in `bundles.yaml` declaring at
least one `env:` variable gets a **wrapper** (`<plugin>/bin/<server-name>`);
any `deps:` entry declaring `env:` gets a **scoped launcher**
(`<plugin>/bin/<command-name>`) — same credential resolution, but it
forwards the caller's own arguments to the real command instead of running
a fixed argument list, since a `deps:` entry backs a CLI a skill drives
directly rather than an MCP server with a fixed invocation. An entry
declaring no `env:` is untouched — a wrapper on a credential-free server
would buy nothing.

**What a wrapper does, concretely** (`build.py`'s `write_bin`, one
generated per entry):

1. Runs `resolver.py` (a copy of `shared/resolver.py`, placed alongside
   every wrapper in the same `bin/` — see below) with its own declared
   variable names as arguments.
2. Parses (never `source`s or `eval`s) the `KEY=VALUE` lines that prints,
   and exports them into its own environment. Parsing rather than sourcing
   means a value containing shell metacharacters can't execute anything.
3. `exec`s the real command — same executable and arguments `bundles.yaml`
   declared, with credential-bearing tokens substituted from the
   now-exported environment.

A generated wrapper for the `database` plugin's `pgquery` server looks like
this:

```sh
#!/bin/sh
# Generated by build.py — do not edit by hand.
set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RESOLVED=$("$DIR/resolver.py" PGQUERY_URI) || exit $?
while IFS='=' read -r key value; do
  [ -n "$key" ] && export "$key=$value"
done <<EOF
$RESOLVED
EOF
export DATABASE_URI="$PGQUERY_URI"
exec docker run -i --rm -e DATABASE_URI crystaldba/postgres-mcp --access-mode=restricted --transport=stdio
```

`.mcp.json` then points at the wrapper instead of `docker`/`npx` directly,
with empty `args` and no `env` block — there's nothing left for Claude Code
to substitute:

```json
"pgquery": { "command": "${CLAUDE_PLUGIN_ROOT}/bin/pgquery", "args": [] }
```

**Why secrets never land in `argv`.** A Docker `-e NAME=${VAR}` pair in
`bundles.yaml` becomes a *bare* `-e NAME` in the generated wrapper — the
bare form pulls the value from the wrapper's own already-exported
environment rather than putting it in the command line, so it never shows
up in another user's `ps` listing. `env`-command-style entries
(`azkusto`'s `command: env KUSTO_..=${VAR} ... npx -y kusto-mcp`) become
plain `export` statements ahead of the real command instead. A value that
has to be argv-visible by necessity — a filesystem path substituted into a
positional argument, or a Docker bind mount (`-v ${DBTOOLS_CONFIG_PATH}:...`)
— stays argv-visible; there's no way around that for a mount, and it isn't
a secret in the way a connection string is.

**The resolver travels with the wrapper, not with `essentials`.**
`build.py` copies `shared/resolver.py` into every plugin that has at least
one credential-bearing entry, alongside that plugin's own generated
wrappers/launchers. A `database` plugin installed without `essentials` still
resolves its own credentials correctly — `essentials` supplies only the UI
skill and the `SessionStart` hook, both conveniences, never a runtime
dependency any other plugin needs to function.

**`skills:`-level `env:` is catalog-only.** A `skills:` entry (a skill that
drives a CLI directly, with no MCP server behind it) can declare `env:` too
— it reaches `.env.example` and `catalog.json` for visibility, and the
`SessionStart` hook nudges on it like anything else — but `build.py`
generates no wrapper for a `skills:`-level declaration; only `mcp:` and
`deps:` entries get one. A skill that needs its declared variable has to
resolve it itself. The one such case shipped today, `last30days`'s
`SCRAPECREATORS_API_KEY`, manages its own credential entirely outside this
design (its own `~/.config/last30days/.env`, its own signup flow) — that's
a pre-existing, self-contained mechanism from the vendored upstream skill,
not something this store drives.

**VS Code gets the same wrapper.** `vscode-mcp.json` is generated from the
same `mcp:` block and points `command` at the identical wrapper path — the
wrapper resolves and exports credentials on its own, so nothing there needs
VS Code's `promptString` input mechanism. Consequence: VS Code and Claude
Code both read the *same* `~/.indie-marketplace/profiles.json` (there's
only one store, keyed by variable name, not by editor).

## The web UI

- One `index.html`, inlined CSS and JavaScript, no build step, no CDN, no
  third-party dependency — the same "Python standard library only" posture
  as the server behind it. It is a **browser** UI, not terminal prompts,
  because reviewing a full credential catalog with required/optional
  labels, descriptions, and per-profile inheritance state is a form, not a
  sequence of one-at-a-time answers.
- **Screen A — profile editor.** Every catalog variable, grouped by plugin
  and tool, for the selected profile: inherited-from-`base` or overridden
  here, required/optional, masked by default with a per-field reveal.
  Create, rename, and delete profiles; bind a profile to one or more
  project directories. Saving a blank field never writes a functionally
  inert empty-string override — it either clears an existing override
  (restoring inheritance) or, on `base`, leaves the variable genuinely
  unset; the UI never lets a click produce a stored value that resolution
  would treat identically to "unset" anyway.
- **Screen B — active profile.** A dropdown of profile names, writing the
  `active` file.
- **How Claude reaches it.** The `secrets-manager` skill starts
  `skills/secrets-manager/server.py` in the background and relays exactly
  one thing: the first line of its stdout, a `127.0.0.1` URL carrying a
  one-time token (`http://127.0.0.1:PORT/?token=...`). Every request must
  present that token and a matching `Host` header (defeats DNS rebinding);
  responses carry `Cache-Control: no-store` and no CORS headers. The server
  shuts down on an explicit "Done" click or after 15 minutes idle — a
  forgotten listener serving credentials on loopback is the failure this
  guards against.
- **API**, all names/state only except the one explicit reveal endpoint:

  ```
  GET  /api/catalog             [{plugin, name, type, env:[{name, required, description}]}]
  GET  /api/profiles            {profile: {projects, values: {VAR: "set-here"|"inherited"|"unset"}}}
  GET  /api/value?profile=&name=   {"value": "..." | null}   — the one per-field reveal
  GET  /api/active               {"active": "client-a" | null}
  POST /api/profile/<name>       {"values": {VAR: "..."|null}, "projects": [...]}  — null clears an override
  POST /api/profile/<name>/rename   {"to": "new-name"}
  DELETE /api/profile/<name>
  POST /api/active                {"profile": "client-a"}
  POST /api/shutdown
  ```

  Writes are validated server-side: profile names must match a safe slug
  pattern, every submitted variable name must already exist in the catalog
  (an unknown key is rejected, not stored), `base` can't be renamed or
  deleted, and `projects` entries must be absolute paths.

## <a id="the-skill"></a>The secrets-manager skill

Bundled with `essentials`, this is what Claude actually runs on your
behalf. Its only value-touching action is starting the server above and
relaying its URL — everything else it does answers a question from
variable *names*, profile *state labels*, project *paths*, or file
*permission bits*, never a value:

| Ask for | Runs | Answers |
|---|---|---|
| Open the manager | `server.py` (backgrounded, first stdout line only) | a URL to open |
| What's unset | `status.py unset [--profile NAME]` | every catalog variable unset for a profile (default: whichever profile the current directory resolves to), tagged required/optional |
| Which profile applies here | `status.py resolve [PATH]` | the profile a directory resolves to, and which precedence rule decided it |
| Health check | `status.py doctor` | stale bound project paths, variables no installed plugin declares anymore, and store files/directories whose permissions have drifted from `0600`/`0700` |

Hard prohibitions, stated in the skill's own instructions regardless of
what a user asks for: never read a value out of `profiles.json`; never
invoke a wrapper or scoped launcher directly (those hand a value to a
*subprocess*, not to a Claude session); never print anything from the
server's own output beyond its one URL line; never write a credential value
on the user's behalf — every write happens through the user's own clicks in
the browser.

## Walkthrough, from a clean machine

1. **Install a plugin.** `claude plugin install database@indie-marketplace`.
   No secrets file exists yet, anywhere — nothing was written outside the
   plugin's own versioned install directory.
2. **First session.** The `SessionStart` hook runs. `database`'s `pgquery`
   server has required variables and none of them are set — but *none set
   at all* is silence, not a nudge (see
   [Nudging](#nudging) below). Nothing appears yet.
3. **Set one variable, leave the rest.** Say you set `PGQUERY_URI` but
   `database` has other servers (`mysql-mcp`, `mssql-mcp`) with their own
   unset required variables. Next session start, those show up:
   `database/mysql-mcp missing: MYSQL_MCP_HOST, MYSQL_MCP_USER, ...` — a
   *partial* configuration, which is exactly the state worth flagging.
4. **Open the UI.** Ask Claude to open the secrets manager. On Screen A,
   fill in `base` with whatever's genuinely global (a Zotero key, an Exa
   key) and the `pgquery` variable if it's the same everywhere.
5. **Create a project profile.** Add `client-a`, override `PGQUERY_URI`
   with that client's connection string, and bind it to
   `/Users/you/work/client-a`.
6. **Use it — no typing required.** `cd /Users/you/work/client-a && claude`
   resolves `client-a` automatically via the bound-path match. A second,
   concurrent session in a different directory resolves independently —
   nothing shared, nothing to contend over.
7. **Override for one session.** Working inside `client-a`'s tree but need
   `base`'s values instead, just this once? `INDIE_PROFILE=base claude` —
   `$INDIE_PROFILE` outranks the path match. See
   [Launch ergonomics](#launch-ergonomics).

## <a id="nudging"></a>Nudging — when the `SessionStart` hook speaks up

Reading `plugins/essentials/scripts/secrets-startup-check.py`, wired to
`SessionStart`'s `startup` matcher in `plugins/essentials/hooks/hooks.json`
(both hand-maintained — see [Repo notes](#repo-notes)):

| State | Meaning | Nudge? |
|---|---|---|
| **fully configured** | every required variable of a tool is set (via the resolved profile or inherited from `base`) | no |
| **partially configured** | some, not all, required variables set | **yes** |
| **entirely untouched** | no required variable set | no — treated as deliberately unused |

Classification is per catalog *entry* (one MCP server, or one CLI tool),
not per plugin — a multi-server plugin like `database` can have `pgquery`
fully configured and silent while `mysql-mcp` sits partial and nudges,
because half-entering one server's credentials is the state that actually
breaks something. The hook derives all of this fresh, every session start,
from `profiles.json`'s contents and each installed, enabled plugin's
`catalog.json` — there's no acknowledgement marker or opt-out list to fall
out of sync with reality. One malformed `catalog.json` from one plugin
doesn't suppress the nudge for every other plugin; that plugin alone is
skipped. Every failure mode here (missing store, unreadable
`installed_plugins.json`, malformed `catalog.json`) is swallowed —
`SessionStart` must never block or error on a shape it doesn't recognize.

## <a id="launch-ergonomics"></a>Launch ergonomics

`$INDIE_PROFILE` is the one thing you have to type by hand, and only in two
cases: working outside any directory a profile is bound to, or overriding
the profile a bound directory would otherwise resolve to for one session.
Inside a bound directory, the profile is selected automatically — there is
nothing to type.

Add this to your shell profile once:

```sh
cc() { INDIE_PROFILE="$1" claude; }
```

```sh
cc client-a   # -> INDIE_PROFILE=client-a claude
cc base       # explicitly force base, even inside a bound directory
```

Two Claude Code sessions started this way never contend over shared state —
`$INDIE_PROFILE` is read once, at process launch, from that process's own
environment.

## Permissions and the trust boundary

- Directory creation: `os.umask(0o077)` around `mkdir`, then an explicit
  `os.chmod(parent, 0o700)` — `0700` from the moment the store directory
  exists.
- File writes: the mode is set on the temp file (`0600` for
  `profiles.json` and `active`) before the atomic rename into place —
  there's no create-then-`chmod` window where the file is briefly
  world-readable.
- `doctor` (via the secrets-manager skill) checks the store root and both
  files against these exact modes and reports drift with the path and the
  mode found — it does not fix permissions itself.
- **"Claude never sees a value" is a boundary enforced by these scripts,
  not a cryptographic proof.** It rests on: no shipped script here has a
  code path that prints a value; the skill's own instructions refuse to
  read one; and the UI's reveal action is a click the user makes, not a
  tool call Claude issues. An agent running arbitrary shell as the same
  user is outside what any of that can stop — the honest posture is the
  same one an unencrypted SSH private key or a `.pgpass` file has.

## Stated limits

- **No mid-session profile switching.** MCP servers launch at session
  start, before any skill can run. Switching profiles means restarting the
  session under a different `$INDIE_PROFILE` (or a different bound
  directory). The UI is a configuration surface, not a runtime switcher —
  this is a consequence accepted by the design, not a bug to route around.
- **A browser on the same machine is required.** There is no headless or
  no-browser configuration path; a bare SSH session means hand-editing
  `profiles.json`.
- **Unix and WSL only.** Generated wrappers are POSIX shell (`#!/bin/sh`,
  `exec`, `os.replace`-backed atomic writes). Native Windows without WSL
  isn't supported.
- **Plaintext at `0600`.** No encryption at rest, no OS keychain
  integration — the same posture as an SSH private key. See `NEXTME.md`
  for what's deliberately deferred here.
- **A `skills:`-level `env:` declaration gets no wrapper.** See
  [Wrappers and scoped launchers](#wrappers-and-scoped-launchers) above —
  it's visible in the catalog, the UI, and the nudge, but nothing exports
  its value automatically unless the skill resolves it itself.
- **A profile can be pointed at the wrong project by hand.** Automatic
  directory binding covers the common case, but a manually-set
  `$INDIE_PROFILE` or `active` file can still select the wrong profile for
  where you're actually working. This is the one regression accepted
  relative to a purely filesystem-derived scheme — the alternative
  (deriving scope only from a project registry with stable identifiers and
  planted symlinks) was rejected as substantially more machinery than the
  whole rest of this feature; see below.

## What was rejected, and why

Recorded so a future session doesn't re-derive and re-propose these:

- **A project registry with stable identifiers and symlinks planted in
  project roots**, plus `--relink`/`--forget-project`/`--adopt-from`
  migration tooling to keep it in sync. This was the whole shape of the
  design that preceded the one in this document. It required a registry
  that could drift from reality, stable IDs that a plugin rename or split
  would invalidate, and symlinks written into project directories — none of
  which the bound-project-path scheme (a plain string comparison against
  `profiles.json`) needs at all.
- **`direnv` / `.envrc`.** Would mean a value-bearing file inside a
  project's own working tree — exactly the exposure surface a credential
  store outside any project directory is designed to avoid.
- **`settings.json`'s `env` key as the credential store.** It's a single
  global environment shared by every MCP server and every Bash tool call,
  which reintroduces the cross-plugin collision surface a per-variable
  global namespace with a build-time duplicate check already eliminates;
  and it would mean writing credential values into a file Claude reads and
  edits routinely — a strictly worse exposure surface than a `0600` file
  outside `~/.claude/` entirely.
- **`configure-secrets.sh`, a terminal-prompt credential wizard.** Superseded
  by the browser UI once "review a full catalog with per-profile
  inheritance state" was the actual requirement — a sequence of one-at-a-
  time prompts has no way to show that.
- **A `scope:` annotation on a variable in `bundles.yaml`.** Scope isn't a
  property of a variable — it's a consequence of which profile a value is
  stored under. Declaring it a second time per-variable would just be
  another place for it to disagree with reality.
- **Per-plugin secrets files** (the design's own earlier draft, before
  settling on one `profiles.json`). Keying credentials by variable name in
  one file, rather than by plugin in many files, is what makes renaming or
  splitting a plugin free — nothing to migrate, because nothing is keyed by
  plugin identity at all.

## <a id="repo-notes"></a>Repo notes

- `bundles.yaml` is the single source of truth for which variables exist;
  see its own header comments for the `env:`/`mcp:`/`deps:` field reference.
  `build.py` fails the build if the same variable name is declared by more
  than one plugin, naming both, so two tools can never silently share one
  credential.
- `plugins/essentials/hooks/hooks.json` and
  `plugins/essentials/scripts/secrets-startup-check.py` are hand-maintained,
  not `build.py`-generated — `essentials` has no `hooks:` block in
  `bundles.yaml` because nothing there is fetched from upstream.
- `shared/resolver.py` and `shared/indie_store.py` are the only two
  first-party implementations of store access. `resolver.py` is
  deliberately self-contained (no imports beyond the standard library, no
  dependency on any other file in this repo) because it's copied verbatim
  into every credential-bearing plugin's `bin/` and must keep working with
  zero access to this repository at runtime. `indie_store.py` is the
  version everything else here — the web server, the tests — actually
  imports.
