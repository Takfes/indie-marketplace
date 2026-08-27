# Plugin secrets architecture

How MCP-server and CLI-tool credentials get from "declared in `bundles.yaml`"
to "available to a running process" — without a value ever passing through a
model's own context, independent of plugin version, marketplace, or which
project the user is in.

## Design constraints

Everything below is built on these, in this order of confidence:

- **Verified on this machine.** `~/.claude/plugins/installed_plugins.json` is
  `{"version": 2, "plugins": {"<plugin>@<marketplace>": [ {scope, installPath,
  version, lastUpdated, ...} ]}}` — the value is an *array*, one record per
  install scope. `~/.claude/settings.json` carries `enabledPlugins` as a
  `{"<plugin>@<marketplace>": bool}` map. Install paths are versioned
  (`cache/<marketplace>/<plugin>/<version>/`), every plugin here is pinned
  `0.1.0`, and updates therefore overwrite in place — a file deleted from the
  repo can survive in an installed copy indefinitely.
- **Documented.** `${CLAUDE_PLUGIN_ROOT}` expands inside a plugin's
  `.mcp.json` and `hooks.json`. `${VAR}` in `.mcp.json` expands from the
  environment of the process that launched Claude Code.
- **Deliberately not relied on.** Whether a `settings.json` `env` entry
  propagates into an MCP subprocess, and whether `$CLAUDE_PROJECT_DIR` or a
  useful `$PWD` reaches one, are untested here. Nothing in this design
  depends on either. Where a value has to arrive somewhere, an explicit
  mechanism puts it there.

## Walkthrough

**Install a plugin**
- `claude plugin install database@indie-marketplace`.
- Landing in the versioned install dir: one generated wrapper per
  credential-bearing MCP server (`mcp/<server>.sh`, mode `0755`), an
  `.mcp.json` whose `command` points at those wrappers, `catalog.json`
  (names, required/optional, renames, mounts), `.env.example` (human-readable
  documentation), and `SECRETS.md`.
- No secrets file exists yet, anywhere. Nothing was written outside the
  install dir.

**First session after install**
- `SessionStart` hook (matcher `startup`) runs `check-secrets.sh --quiet`.
- It enumerates installed *and* enabled plugins, reads each one's
  `catalog.json`, and applies the zero/partial/complete rule (below).
- `database` has required vars and no secrets file at all → one line of
  `additionalContext`: `database: 9 required variables unset — see the
  secrets skill`. No values, no paths to values, no per-var detail.
- `research` declares three variables, all optional → never mentioned.
- Everything satisfied → the hook emits nothing and adds no perceptible
  delay (a handful of small file reads, no subprocess).

**Configure credentials**
- The user runs, in their own terminal, never through a Claude tool call:
  `configure-secrets.sh database --server pgquery`
- The script refuses to run at all unless stdin *and* stdout are a TTY.
- It prompts for `PGQUERY_URI` only — `--server` scopes the run to one
  server's variables instead of marching through all 13 in the plugin.
- Input is hidden for variables marked secret, echoed for those marked
  `secret: false` (a config-file path, a binary path, an enum value) so a
  typo is visible.
- Each accepted value is written immediately: whole file rendered to a temp
  file in the same directory under `umask 077`, then `rename`d over the
  target. Ctrl-C keeps everything entered so far.
- Result: `~/.local/share/claude-plugin-secrets/indie-marketplace/database.env`,
  mode `0600`, inside a `0700` directory tree.

**Use it**
- The user asks for something that needs the Postgres server.
- Claude Code launches `mcp/pgquery.sh` from the plugin's install dir.
- The wrapper parses (never sources) the secrets file, asserts every required
  variable is set, exports `PGQUERY_URI`'s value as `DATABASE_URI`, and
  `exec`s `docker run … -e DATABASE_URI …` — the name is in argv, the value
  is only in the environment.
- A missing required variable stops here with a one-line stderr message
  naming the variable and the exact command to fix it, and exit status 1.

**Plugin update**
- New content overwrites the versioned install dir; `catalog.json` may gain,
  drop, or re-annotate variables.
- Nothing to migrate: the secrets file was never inside the install dir, and
  its path has no version component.
- The next check re-derives required names from the *current*
  `catalog.json`. A newly-required variable shows as missing; a dropped one
  shows as stale, with the exact `--delete` command. No registry, no sync
  step, nothing to keep in agreement.

**Rotate or change a value**
- `configure-secrets.sh database --force MYSQL_MCP_PASS` re-prompts exactly
  that one variable.
- `--force` with no variable name re-prompts everything in scope;
  `--force --server mssql-mcp` re-prompts one server's set.

**Rename or split a plugin**
- The secrets file is keyed by plugin name, so a rename orphans it and a
  split leaves one file holding variables that now belong to several
  plugins.
- `status` detects both: any `<marketplace>/*.env` with no installed plugin
  of that name is reported as orphaned, with the adopt command spelled out.
- `configure-secrets.sh <new-plugin> --adopt-from <old-plugin>` copies over
  exactly the variables the new plugin's `catalog.json` declares, line for
  line, printing names only. Run it once per plugin the split produced, then
  `--delete` the old file.
- Both operations are value-blind — they move lines between files and never
  render a value to stdout — so the skill may run them directly.

**A value needs to differ per project**
- There is no project-scoped secrets file (see *Deliberately out of scope*).
- The supported answer: launch Claude Code for that project with
  `CLAUDE_PLUGIN_SECRETS_HOME` pointed at a different root. It is one
  variable, set explicitly by the user, and it moves the whole store — no
  per-repo file is read, so no repository can influence what a wrapper
  loads.

**Uninstall**
- The install dir and its wrappers go away. The secrets file does not.
- `status` reports it as orphaned; the skill deletes it on request — a
  path-only operation, no value read.

## The pieces

| Piece | Job | Lives in | Written by |
|---|---|---|---|
| Secrets file | Real values, one file per plugin, marketplace-qualified path | `$SECRETS_ROOT/<marketplace>/<plugin>.env` | `configure-secrets.sh` only |
| `catalog.json` | Machine-readable declaration: per entry, which vars, required, secret, renamed-to, mounted-at | Plugin's `.claude-plugin/` | `build.py`, from `bundles.yaml` |
| `.env.example` | Same information, human-readable; documentation only | Plugin root | `build.py`, from `bundles.yaml` |
| MCP wrapper | Loads the plugin's variables, asserts required ones, `exec`s the real server | `<plugin>/mcp/<server>.sh`, referenced from `.mcp.json` | `build.py` codegen |
| `bin/with-secrets` | Same load, for CLI-driven skills with no MCP launch point | `<plugin>/bin/with-secrets` | `build.py` codegen |
| `lib-secrets.sh` | The parser, the "set" predicate, the permission check — one implementation | `essentials/scripts/` | `build.py`, from the same template it inlines into wrappers |
| `check-secrets.sh` | Presence check; `--quiet` (hook JSON) and `--report` (human) on one code path | `essentials/scripts/` | Hand-maintained |
| `configure-secrets.sh` | The only thing that ever asks for or writes a real value | `essentials/scripts/` | Hand-maintained |
| `SessionStart` hook | Runs the quiet check on real session start | `essentials/hooks/` | Fires on `startup` only |
| Secrets skill | status / locate / point-to-configure / delete / adopt / doctor | `essentials/skills/` | Invoked by the user or by the nudge |

## Where secrets live

- Root: `$SECRETS_ROOT` = `${CLAUDE_PLUGIN_SECRETS_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/claude-plugin-secrets}`.
- File: `$SECRETS_ROOT/<marketplace>/<plugin>.env`.
- **Marketplace-qualified by directory, not by a joined key.** `indie-marketplace/web-search.env`
  is unambiguous; a flat `web-search-indie-marketplace` is not — plugin and
  marketplace names both contain hyphens, so the join has no unique split
  point. The nested form also makes "list every file this marketplace owns"
  a plain `ls`, which is what orphan detection needs.
- **Outside `~/.claude/` on purpose.** That tree is routinely swept into
  dotfiles repos and sync services, and `~/.claude/plugins/` is managed by
  Claude Code itself (it prunes and rewrites install caches). A credential
  store should not live in either.
- **`~/.claude/plugins/data/<plugin>-<marketplace>/` was considered and not
  used.** It already carries the marketplace-qualified key this design needs,
  but it is Claude Code's own directory: its creation mode, its lifecycle on
  uninstall, and its stability as an interface are all outside this repo's
  control, and it is inside the tree ruled out above. The naming *idea* is
  adopted; the location is not.
- Version never appears in the path. Neither does an install path, a scope,
  or a project directory.

## File format

- Line-oriented `KEY=VALUE`. Not a shell script — **nothing ever `source`s
  it.**
- Writer rules: key matches `^[A-Za-z_][A-Za-z0-9_]*$`; the value is written
  verbatim after the first `=`, with no quoting, no escaping, no
  substitution. A value containing a newline or NUL is **rejected at input
  time** with an explanation, not silently mangled. Every other byte —
  backtick, `$(`, `"`, `'`, `#`, leading/trailing space — is stored and
  returned exactly as typed.
- Reader rules: skip empty lines and lines whose first character is `#`; a
  line with no `=` is a parse error naming the line number, not a skip; the
  key is everything before the first `=`, the value is everything after it,
  untrimmed and unquoted; on a duplicate key the last occurrence wins.
- The consequence is deliberate: because the file is parsed rather than
  executed, a hostile or corrupt value can at worst produce a wrong value —
  never code execution, and never the multi-line/quoting corruption that a
  `source`-based loader has to warn about.

**One definition of "set", used everywhere**

> A variable is **set** iff its key is present in the file *and* its value
> contains at least one non-whitespace character.

- `NAME=` → unset. `NAME=   ` → unset. Key absent → unset.
- This exact predicate is what `check-secrets.sh` reports, what
  `configure-secrets.sh` treats as "already configured", and what a wrapper's
  required-variable assertion tests. It exists once, in `lib-secrets.sh` and
  in the identical inlined copy inside each generated wrapper — both emitted
  from a single template in `build.py`, so they cannot drift.

## Permissions and the trust boundary

- Directory creation: `(umask 077; mkdir -p "$SECRETS_ROOT/<marketplace>")` —
  `0700` from the moment it exists.
- File writes: `umask 077` is set **before** the temp file is created, so it
  is `0600` at creation. There is no create-then-chmod window. The temp file
  is created in the target's own directory (same filesystem) and `rename`d
  into place, which is atomic and preserves the mode.
- Every reader — wrapper, `check-secrets.sh`, `with-secrets` — verifies
  before reading that the file is owned by the current user and is mode
  `0600` (and the directory `0700`). A failure is a hard stop with the exact
  `chmod` to run, never a silent fallback to unset. (Mode/owner are read via
  `stat -f '%Lp %u'`, falling back to `stat -c '%a %u'` — the BSD/GNU split
  is probed once in the shared template.)
- **`configure-secrets.sh` guards value entry technically, not by
  convention.** Any code path that would prompt starts with
  `[ -t 0 ] && [ -t 1 ] || exit 1` and an explanation. There is no
  `--set VAR=VALUE` flag and no stdin ingestion — the two shapes an agent
  would reach for both fail. Value-blind paths (`--delete`, `--adopt-from`,
  `--status`) do not require a TTY, because they never render a value; that
  is what keeps rotation and cleanup cheap for the skill to do.
- **A deny rule pairs with the documented policy.** The user adds this once
  to `~/.claude/settings.json` (paths in permission rules are literal —
  no `~` expansion):

```json
"permissions": {
  "deny": ["Read(//Users/<you>/.local/share/claude-plugin-secrets/**)"]
}
```

- The skill's `doctor` function checks for that rule and prints it
  pre-filled with the resolved absolute path if it is missing — so the rule
  has an owner and a verifiable state, rather than living in prose.
- Honest scope of that rule: it stops the `Read` tool. It does not stop an
  arbitrary `Bash` invocation running as the same user; command-pattern deny
  rules cannot cover every way a shell can read a file. What holds there is
  that no script in this design ever prints a value, and the skill is
  instructed never to read the file — policy, backed by the fact that there
  is no *convenient* path to a value.

## Declaring variables in `bundles.yaml`

An `mcp:`/`skills:`/`deps:` entry's `env:` map keeps its current shape; the
value, previously always null, may now carry a small spec:

```yaml
env:
  PGQUERY_URI:                                  # null → required, secret, no rename
  DBTOOLS_CONFIG_PATH: { secret: false, mount: "/tools.yaml:ro" }
  ZOTERO_API_KEY:      { required: false }
  AZKUSTO_TENANT_ID:   { required: false, as: AZURE_TENANT_ID }
  AZAKS_BIN:           { secret: false }        # also used as the entry's `command`
```

- `required` (default `true`) — drives the nudge and the wrapper's hard
  stop. Defaulting to required is the safe direction: a genuinely required
  variable can never become optional by omission.
- `secret` (default `true`) — `false` means echo the input while prompting
  and allow the value in argv. Paths, binary locations, and enum values are
  `secret: false`; anything bearing a credential is not.
- `as:` — the name the *launched process* should see. Covers container-side
  names fixed upstream (`PGQUERY_URI` → `DATABASE_URI`) and the several
  Azure/Kusto renames that today are hand-written into a `command: env`
  argument list.
- `mount:` — the value is a host path to bind-mount at the given container
  target. Docker entries only. `build.py` rejects `mount:` together with
  `secret: true`, because a mount spec is unavoidably argv-visible.

A sibling block carries values that are **not** user input:

```yaml
env_fixed:
  KUSTO_ALLOW_WRITE_OPERATIONS: "false"
  ZOTERO_LOCAL: "true"
```

- These are the security-load-bearing literals that today hide inside
  `command: env` argument lists and inline `-e NAME=false` flags
  (`KUSTO_ALLOW_WRITE_OPERATIONS`, `mysql-mcp`'s three `ALLOW_*_OPERATION`
  flags, `ZOTERO_LOCAL`). They are declarations, committed and diffable, not
  credentials.
- **Precedence is fixed and one-directional:** a wrapper loads secrets
  first, then applies `env_fixed` — so no value in a user's secrets file can
  loosen a server that upstream ships permissive by default. `build.py`
  additionally errors at build time if a name appears both in `env_fixed`
  and as an `env:` name or `as:` target.

`catalog.json` carries all of this verbatim, one object per entry, values
never included:

```json
{ "name": "pgquery", "type": "mcp",
  "env": [ { "name": "PGQUERY_URI", "required": true, "secret": true,
             "as": "DATABASE_URI" } ] }
```

- It is written for **any** plugin that declares an env var anywhere, not
  only those flagged `catalog: true` — a credential-bearing plugin without a
  catalog would be invisible to every tool here.
- It is the single source every consumer reads. `.env.example` stays as
  human documentation (regenerated with `# required` / `# optional`
  annotations and a header pointing at `configure-secrets.sh`), but nothing
  parses it — per-server grouping and optionality only survive in
  `catalog.json`.

## Wrapper: scope and shape

**Which entries get one**

- Exactly those declaring at least one `env:` variable. `context7`,
  `azcloud`, `notebooklm` and every other credential-free server keep a
  plain `.mcp.json` entry with no wrapper at all.
- **Why not narrower.** `${VAR}` in `.mcp.json` expands from the environment
  of the process that launched Claude Code. It cannot read a file this
  design wrote — that gap is the premise of the whole design, not an
  unverified assumption. Anything that needs a value *from the store* needs
  something that reads the store.
- **Why not `settings.json`'s `env` instead.** Three reasons, independent of
  each other: it is a single global environment shared by every MCP server
  and every Bash tool call, which reintroduces exactly the cross-plugin
  collision surface the per-plugin file eliminates; it would require writing
  credential values into a file Claude reads and edits routinely, which is a
  strictly worse exposure surface than a `0600` file behind a deny rule; and
  whether it reaches an MCP subprocess at all is unverified here. The first
  two would be disqualifying even if the third were confirmed.
- **Why not universal.** A wrapper on a credential-free server buys nothing
  and costs a generated file, an `exec` hop, and a failure mode.

**Shape**

- A generated **file** per server — `<plugin>/mcp/<server>.sh` — not an
  inline `bash -c '…'` string in `.mcp.json`. A shell program embedded in a
  JSON string needs escaping that is easy to get subtly wrong, is
  unreviewable in a diff, and grows unreadable the moment it has a
  conditional in it.
- `.mcp.json` addresses it the only way a versioned install dir can be
  addressed: `"command": "${CLAUDE_PLUGIN_ROOT}/mcp/<server>.sh"`, with
  `"args": []`. The real command and its real arguments live inside the
  wrapper, because the docker branch has to build parts of the argument list
  from loaded values.
- `build.py` writes the file and then explicitly `chmod`s it `0755` —
  `Path.write_text` does not set the executable bit. The mode is recorded in
  git, so it survives the clone into the plugin cache.
- The shared loader is **inlined** into every wrapper rather than sourced
  from `essentials`. A `database` wrapper cannot assume `essentials` is
  installed, or find it if it is. Duplication in generated output is free;
  the single source is the template in `build.py`.
- The wrapper's only inputs are its own baked-in variable list and the
  secrets file. It reads no `catalog.json` at runtime and has no dependency
  on any other plugin.

**Plain command branch** — `web-search`/`exa`:

```bash
#!/usr/bin/env bash
# Generated by build.py from bundles.yaml — do not edit.
set -euo pipefail
SECRETS_FILE="${CLAUDE_PLUGIN_SECRETS_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/claude-plugin-secrets}/indie-marketplace/web-search.env"
# … inlined lib-secrets.sh: parse, "set" predicate, ownership/mode check …

secrets_require "$SECRETS_FILE" exa EXA_API_KEY
secrets_export  "$SECRETS_FILE" EXA_API_KEY
exec npx -y exa-mcp-server
```

- `secrets_require FILE SERVER NAME…` — for each unset name, one stderr
  line (`web-search/exa: EXA_API_KEY is not set — run: configure-secrets.sh
  web-search --server exa`) then `exit 1`. Never a warning that continues
  into a less legible downstream failure.
- `secrets_export FILE NAME[:AS]…` — exports each name that is set, under
  its `as:` name where declared. An unset **optional** variable is not
  exported at all, so the downstream tool sees "absent" and takes its own
  default, rather than seeing an empty string.
- No `2>/dev/null` anywhere. A missing file, a bad mode, a foreign owner and
  a malformed line each produce a distinct, named message. These messages
  contain variable names and paths, never values.

**Docker branch** — `database`/`pgquery`, `dbtools`, `mysql-mcp`:

```bash
secrets_require "$SECRETS_FILE" pgquery PGQUERY_URI
secrets_export  "$SECRETS_FILE" PGQUERY_URI:DATABASE_URI
exec docker run -i --rm -e DATABASE_URI \
  crystaldba/postgres-mcp --access-mode=restricted --transport=stdio
```

- **`-e NAME`, never `-e NAME=value`.** The bare form forwards the value
  from the wrapper's own environment, so a password-bearing DSN never
  appears in argv and never shows up in a local `ps` listing.
- `env_fixed` entries *do* go in argv as `-e NAME=value` — they are
  non-secret by construction, and having them visible in a process listing
  is a feature for anything as load-bearing as
  `ALLOW_DELETE_OPERATION=false`.
- A `mount:` variable becomes `-v "$VALUE:<target>"`, which is argv-visible
  by necessity — hence the build-time rule that a mounted variable must be
  declared `secret: false`:

```bash
secrets_require "$SECRETS_FILE" dbtools DBTOOLS_CONFIG_PATH
secrets_export  "$SECRETS_FILE" DBTOOLS_CONFIG_PATH
exec docker run -i --rm -v "$DBTOOLS_CONFIG_PATH:/tools.yaml:ro" \
  us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:latest \
  --stdio --config /tools.yaml
```

**`${VAR}`-as-command** — `azdevops`/`azaks`, where the executable path is
itself supplied by the user: the wrapper requires and exports the variable,
then `exec "$AZAKS_BIN" --transport stdio`. This case *cannot* work through
`.mcp.json` substitution at all when the value lives in the store, which is
why it is called out separately.

**All-optional server** — `research`/`zotero` has no `secrets_require` line
at all, because none of its three variables is required:

```bash
secrets_export "$SECRETS_FILE" ZOTERO_API_KEY ZOTERO_LIBRARY_ID ZOTERO_LIBRARY_TYPE
export ZOTERO_LOCAL=true       # from env_fixed, applied after the store
exec zotero-mcp
```

**Intra-plugin exposure**, stated plainly: a plugin's secrets file is
per-plugin, so a wrapper loads only names it declares — `pgquery`'s process
gets `DATABASE_URI` and nothing else, not `MYSQL_MCP_PASS`. The file groups
several servers' variables; the wrappers do not.

## Bare CLI credentials

- Some variables belong to a skill that drives a CLI directly, with no MCP
  server to wrap — `web-search`'s `SCRAPECREATORS_API_KEY`, consumed by a
  vendored upstream script.
- Each credential-bearing plugin gets a generated
  `<plugin>/bin/with-secrets` (`0755`): the same loader, then
  `exec "$@"`. Any command run through it sees the plugin's variables:

```bash
"$CLAUDE_PLUGIN_ROOT"/bin/with-secrets python scripts/fetch.py …
```

- This deliberately avoids editing the vendored script. A community skill is
  copied verbatim on every fetch (`shutil.copytree`, add/overwrite only), so
  a `source` line added inside it would be silently reverted on the next
  refresh. `bin/with-secrets` lives at the plugin root, which upstream
  content never touches.
- The convention is documented in the plugin's generated `SECRETS.md` (also
  at the plugin root, also outside upstream's reach) and surfaced by the
  skill's `status` output for any plugin with CLI-only variables.
- Residual gap, acknowledged: whether a given invocation actually goes
  through the launcher is a convention, not an enforcement. It is the one
  place this design cannot close by construction.

## Required, optional, and when to nudge

Required-ness is per variable, and variables belong to a server (or skill,
or CLI entry) — both facts come from `catalog.json`. That gives three states
per entry:

| State | Meaning | Nudge? |
|---|---|---|
| **complete** | every required variable set | no |
| **partial** | some but not all required variables set | **yes** — a real misconfiguration |
| **zero** | no required variable set | no — treated as deliberately unused |
| *(no required variables at all)* | e.g. `research`/`zotero` | never |

- Plus one bootstrap case: a plugin that has at least one required variable
  **and no secrets file at all** is nudged — that is the intended
  onboarding, and it stops the moment the file exists.
- The zero/partial/complete rule is what makes a multi-server plugin usable.
  A Postgres-only user configures `pgquery`, and `mysql-mcp`, `mssql-mcp`,
  `dbtools` sit at **zero** — untouched, therefore silent — instead of
  nagging forever. Half-entering a MySQL configuration, which genuinely
  breaks that server, is what raises a flag.
- No state file, no acknowledgement marker, no opt-out list: all three
  states are derived from the secrets file's contents on every run.

**Nudge output** (hook, `additionalContext`) — one line per affected plugin,
counts only:

```
database: 4 required variables unset for mysql-mcp — see the secrets skill
```

**`status` output** (on demand) — per plugin, grouped by entry:

```
database  ~/.local/share/claude-plugin-secrets/indie-marketplace/database.env  (0600, ok)
  pgquery     ready        PGQUERY_URI ✓
  dbtools     unconfigured DBTOOLS_CONFIG_PATH — (required)
  mysql-mcp   incomplete   MYSQL_MCP_HOST ✓  MYSQL_MCP_USER ✓  MYSQL_MCP_PASS —  MYSQL_MCP_DB —
research  (no file — nothing required)
  zotero      ready        ZOTERO_API_KEY — (optional, upstream default applies)
```

- "ready" is the verdict whenever every **required** variable is set, no
  matter how many optional ones are unset. An unset optional variable is
  rendered as information, never as a problem to fix.
- Stale keys (present in the file, no longer declared) get their own line
  and the exact `--delete` command.
- Counts and presence only. No value, no length, no masked fragment.

## `configure-secrets.sh` — pinned behavior

```
configure-secrets.sh <plugin> [--server NAME] [--force [VAR]]
                              [--delete [VAR]] [--adopt-from OLD]
                              [--import PATH] [--status] [--yes]
```

- Reads which variables to handle from the installed plugin's
  `catalog.json`; writes to `$SECRETS_ROOT/<marketplace>/<plugin>.env`. The
  marketplace is resolved from `installed_plugins.json`; if the plugin name
  is installed from more than one marketplace, the script refuses and asks
  for `<plugin>@<marketplace>`.
- Default run: prompts only for variables that are unset, in catalog order,
  grouped by server with a header. Already-set variables print
  `already set — Enter to keep` and are not re-prompted.
- Prompting: hidden (`read -s`) for `secret: true`, echoed for
  `secret: false`. Bare Enter on an unset variable **skips** it (leaves it
  absent), and says so. A value is stored exactly as typed — no trimming —
  with one refusal: a value containing a newline or NUL is rejected with an
  explanation and re-prompted.
- `--server NAME` scopes everything (prompting, `--force`, `--status`) to one
  entry's variables.
- `--force` re-prompts everything in scope; `--force VAR` re-prompts exactly
  one variable — the cheap path for rotating a single credential.
- **Write timing:** each accepted value is committed immediately as a whole-
  file atomic rewrite (`umask 077` → temp file in the same directory →
  `rename`). Ctrl-C mid-sequence keeps every value entered before it; the
  next run resumes at the first unset variable. There is no state in which
  a partially written file is visible to a reader.
- **Merge and prune:** the file is script-owned and fully re-rendered on
  every write — generated header, one commented group per entry in catalog
  order, keys in catalog order. Hand-added comments and hand-chosen ordering
  are not preserved. Keys no longer declared are **retained**, moved to a
  trailing `# no longer declared by this plugin` block, and reported by
  `status`; they are never dropped silently and never dropped automatically.
- **Concurrency:** an exclusive lock is taken for the duration of a write —
  `mkdir "$file.lock"`, released by an `EXIT` trap, atomic on every
  filesystem this targets (`flock` is not present by default on macOS). A
  second concurrent run reports the lock and exits rather than losing the
  first run's entries.
- `--delete VAR` removes one key; `--delete` alone removes the file, with a
  confirmation that `--yes` can pre-answer. Value-blind, so no TTY required.
- `--adopt-from OLD` copies from `<marketplace>/OLD.env` exactly those keys
  the current plugin's catalog declares, verbatim, printing names only —
  the rename and split path.
- `--import PATH` pulls declared keys out of a legacy `.env` file, prints
  names only, and then tells the user to delete the source themselves; it
  refuses a file with an unparseable line, and it requires a TTY (it is a
  human cleanup action against an arbitrary path).
- Ends by calling `check-secrets.sh --report <plugin>` so the run's result is
  shown in the same presence-only vocabulary the skill uses.

## `check-secrets.sh` and the `SessionStart` hook

- One code path, two modes: `--quiet` (emits `hookSpecificOutput` JSON, and
  only when something needs saying) and `--report [plugin]` (human-readable,
  all plugins or one). Neither mode can print a value — there is no code
  path in the script that renders one.
- Enumeration reads `~/.claude/plugins/installed_plugins.json` directly. No
  `claude plugin list --json` subprocess: a blocking startup hook should not
  pay process-spawn latency, and the whole check is otherwise a handful of
  small file reads.
- That file's format is undocumented, so reading it is **defensive**: if it
  is absent, unparseable, or not `version: 2`, the hook exits 0 in silence.
  A startup hook must never block or error on a shape change. `--report`
  says so explicitly instead, and points at `claude plugin list`.
- **Disabled plugins are filtered out** — a plugin is considered only if
  `settings.json`'s `enabledPlugins` maps `<plugin>@<marketplace>` to true.
  A plugin that is installed but switched off never nags.
- **Multiple install records** (the value is an array — user and project
  scope can coexist at different versions): the record with the newest
  `lastUpdated` supplies the `catalog.json` to read. If the records disagree
  on which variables exist, `--report` adds one line naming both install
  paths. The secrets file itself is unaffected — it is keyed by plugin, not
  by install.
- Hook wiring: `SessionStart`, matcher `startup` only, so `/clear` and
  compaction never re-nag mid-conversation.
- The hook never writes anything and never collects a value — the same
  boundary as the skill.
- No install/update-triggered hook exists: every check is a fresh scan of
  current state, so there is nothing that needs invalidating.

## Secrets-management skill

Safe for Claude to run directly (none of these can render a value):

- **status** — the report above, across every installed and enabled plugin.
- **locate** — prints the secrets file path and its mode. A path is not a
  value; the deny rule is what makes the path uninteresting.
- **point-to-configure** — prints the exact `configure-secrets.sh` command
  for the user to run, including `--server`/`--force VAR` where that is the
  cheaper path. Never runs it.
- **delete / reset** — removes a key or a file. Deleting touches a path,
  never a value, so making the user drop to a terminal for it would buy
  nothing and make rotation worse.
- **adopt** — the rename/split migration; moves lines between files, prints
  names.
- **doctor** — checks directory and file modes and ownership, checks that
  the `Read(...)` deny rule is present in `settings.json`, and prints
  whatever needs fixing with the exact command or JSON snippet.

Refused unconditionally, by the skill's own instructions:

- Running any prompting path of `configure-secrets.sh` — including when the
  user explicitly asks it to. The technical TTY guard makes the attempt fail
  anyway; the instruction exists so the refusal is legible rather than
  confusing.
- Reading the secrets file by any means, including "just to check whether it
  parses". `doctor` answers every legitimate version of that question.

No "register a plugin" step exists: the required-variable list is re-derived
from whatever is installed on every single run, which removes the entire
class of bug where a registry and reality disagree.

## Two configurations of the same declarations

- `vscode-mcp.json` is still generated from the same `mcp:` block, and it
  **does not use the wrapper**. VS Code has its own `promptString` inputs and
  its own credential storage; routing it through a Unix wrapper and a
  `0600` file would replace a working native flow with a worse one.
- What the shared declarations give it: `as:` renames are applied (the input
  keeps the declared name, the server's `env` key is the renamed one),
  `env_fixed` values are emitted literally into the server's `env` block, and
  a `mount:` variable becomes an input substituted into the `-v` argument.
  Docker entries use the `-e NAME` forwarding form there too, since VS Code
  sets the server process's environment.
- Consequences, stated rather than hidden: the two editors keep **separate
  credential stores**, so a value configured in one is not available in the
  other; `check-secrets.sh` and the skill report on the Claude Code store
  only; and VS Code has no notion of an optional variable, so every declared
  variable still becomes a `promptString` there.

## Migration from the previous convention

- The earlier instruction was "copy `.env.example` to `.env` inside the
  plugin directory and fill it in". Anyone who followed it has real values in
  a versioned install path that an update can overwrite.
- Path forward: `configure-secrets.sh <plugin> --import <path-to-old-.env>`,
  then delete the old file by hand. The script will not delete anything
  outside its own root.
- `bundles.yaml`'s header block needs a matching edit in the same change —
  its "Env var files (per plugin…)" section still describes the `.env`
  half of that convention, and the "To add a CLI credential" line still
  implies it. `.env.example` keeps its entry, with its job restated as
  documentation; `.env` no longer exists as a concept anywhere in this
  design. `.gitignore`'s `.env` rule is harmless and stays.
- Stale generated artifacts are a real, observed phenomenon: because every
  plugin here is pinned `0.1.0` and updates overwrite in place, a file
  deleted from the repo can persist in an installed copy indefinitely.
  Wrappers are therefore keyed by server name and regenerated wholesale, and
  the skill's `doctor` flags a wrapper in the install dir that the current
  `catalog.json` does not account for.

## What this does not guarantee

- **"Claude never sees a value" is a boundary, not a proof.** It rests on
  three things together: no shipped script has a code path that prints a
  value, the prompting paths fail without a TTY, and a deny rule blocks the
  obvious read. An agent running arbitrary shell as the same user is outside
  what any of those can stop.
- **Downstream tools are not under this design's control.** A database
  client can echo a DSN in a connection error, an MCP server can log its own
  configuration, and a container runtime can print its own invocation on some
  failure classes. Keeping values out of argv removes the largest of those
  surfaces; it does not remove the class. Wrapper stderr lands in Claude
  Code's MCP logs, so a *downstream* tool's error text can reach a transcript
  even though this design's own messages never carry a value.
- **Unix shells only.** `bash`, `exec`, `rename`, POSIX modes — consistent
  with the `docker`/CLI patterns this marketplace already ships.
- **The store is a single directory the user is responsible for excluding**
  from any dotfiles or sync setup. Placing it outside `~/.claude/` makes that
  easy; it does not make it automatic.
- **The CLI launcher convention is a convention.** See *Bare CLI
  credentials*.

## Deliberately out of scope

- **Project-scoped secrets files.** A `<project>/.claude/secrets/<plugin>.env`
  tier is cut, not deferred-with-a-shrug. Reading a credentials file out of
  whatever repository happens to be the working directory means any cloned
  repository can supply values to a process this design launches — including,
  for `azaks`, the *executable path itself*. Parsing instead of sourcing
  removes the code-execution half of that, but not the value-substitution
  half. It also depended on cwd or `$CLAUDE_PROJECT_DIR` reaching an MCP
  subprocess, which is unverified, appeared in no user story, and left the
  `.gitignore` obligation without an owner. The supported per-project answer
  is `CLAUDE_PLUGIN_SECRETS_HOME`, set explicitly by the user. Re-entry
  criterion: a concrete case where one project genuinely needs different
  values *and* the whole-store switch is too coarse.
- **Selective enablement of one server within a multi-server plugin.** Claude
  Code's install granularity is per plugin. The zero/partial/complete rule
  makes an unconfigured server silent and harmless, which covers the practical
  complaint; it does not stop the server from being listed. Splitting the
  plugin remains the only real lever.
- **Automated CLI installation.** `deps.json` documents what to install;
  nothing is ever installed on the user's behalf.
- **A cross-marketplace standard.** Everything here is keyed by marketplace,
  so a second marketplace could adopt the same layout — but nothing is
  specified for, or tested against, plugins this repo does not build.
