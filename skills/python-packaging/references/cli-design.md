# CLI Surface Design

Argument ergonomics for a Python CLI's public surface -- the decisions that shape how a tool
*feels* to use, as opposed to `details.md`'s Pattern 6/7, which cover the mechanics of wiring an
entry point (`[project.scripts]`, `click`/`argparse` boilerplate). Read this first when
*designing* the surface; read Pattern 6/7 when you're ready to wire it up.

## Positionals vs. options

- **Positional arguments**: reserve for the one or two inputs every invocation needs and whose
  meaning is unambiguous from position alone (`mytool convert input.csv output.json`). Beyond
  two, ambiguity climbs fast -- move the rest to named options.
- **Options** (`--output`, `-o`): everything else, including anything with a sensible default.
  Every optional flag needs a default documented in its `help=` text, not just in a README.
- **Flags** (boolean switches, `--force`, `--verbose`): name them so the default reads naturally
  as "off" (`--force` defaulting `False` beats `--no-force` defaulting `True`).

## Subcommands vs. flags

Reach for **subcommands** (`mytool sync`, `mytool status`) when the tool does genuinely different
jobs that happen to share infrastructure -- each gets its own argument surface, its own `--help`.
Reach for **flags on one command** when it's one job with variations (`mytool build --release`).
Mixing the two -- a flag that silently changes which positional arguments are expected -- is the
ergonomics smell to avoid; if a flag changes the shape of the rest of the invocation, that's a
subcommand wearing a flag's clothes.

## Short and long forms

Give a flag a short form (`-o`) only if it's used often enough to earn it -- burning single
letters on rare flags forces awkward choices later when a genuinely common one wants that letter.
Every flag gets a long form (`--output`); short forms are an addition, never a replacement.

## Help and version

- Every subcommand carries its own `--help`, not just the root command -- a user one level deep
  shouldn't have to back out to discover it.
- `--version` always present, sourced from the package's actual installed version
  (`importlib.metadata.version("pkg-name")`), never a hardcoded string that drifts from
  `pyproject.toml`.

## Exit codes

`0` on success, non-zero on any failure -- never exit `0` after printing an error, and never
require parsing stdout to know whether the run failed. Give distinct exit codes to distinct
failure classes only when a caller might realistically branch on them (CI scripting against "no
changes found" vs. "hard failure"); one generic non-zero code is fine otherwise. Match this
plugin's own `analyze_all.py`/`quality_loop.py` convention: `sys.exit(1)` when the run found
something actionable, `0` when it didn't.

## Error messages

Same standard as any error message in this project (see the repo's own coding conventions): say
what failed, why, and what to try next. Print errors to **stderr**, reserve **stdout** for the
tool's actual output -- a script piping stdout into another command shouldn't have to filter out
error text.

## Output format: human vs. machine

Default to a readable, human-facing format. When the tool's output might plausibly be piped into
another program or parsed by an agent, add a `--format json`/`--json` flag rather than making the
human-readable format the only option or the machine-readable format the default. This is already
this marketplace's own convention -- `python-scan`'s `analyze_all.py`, `python-quality-tools`'s
`quality_loop.py`, and this skill's sibling `python-performance-optimization`'s
`compare_benchmarks.py` all expose `--format text|json` (or `--json`) on the same principle:
readable by default, parseable on request, never guess which one a caller wants.

## Config precedence

When a value can come from more than one source, document the precedence order explicitly (in
`--help`, not just in prose docs) and keep it consistent across the tool: **CLI flag > environment
variable > config file > built-in default**. A user who passes `--timeout 30` should never have a
config file silently override it.

## Destructive actions

Anything that deletes, overwrites, or force-pushes gets its own explicit flag (`--force`,
`--yes`) or a confirmation prompt -- never a default-on behavior a user discovers only after data
is gone.

## Picking a library

| Need | Reach for |
|---|---|
| Zero dependencies, a script with a handful of flags | `argparse` (stdlib) |
| Subcommands, nested groups, shell completion, a tool meant to grow | `click` |
| Type-hint-driven definitions, less boilerplate than `click`, modern defaults | `typer` (built on `click`) |

`argparse` is always available and is the right default for a single-purpose script. Reach for
`click`/`typer` once the tool has real subcommand structure or you want type-hint-driven argument
parsing -- see Pattern 6/7 in `details.md` for wiring either into `[project.scripts]`.
