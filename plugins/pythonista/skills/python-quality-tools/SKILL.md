---
name: python-quality-tools
description: Run the deterministic Python tooling loop -- ruff format, ruff check --fix, mypy, a secret scan, and a dependency audit -- against a file or project, fixing what's auto-fixable and reporting what isn't. Bootstraps every tool through uvx rather than requiring it pre-installed. Use as the mechanical fix pass in a cleanup or ship pipeline, or whenever the user asks to "run the linter/formatter/type checker", "fix lint issues", "check for secrets", or "audit dependencies" on Python code.
---

# Python Quality Tools

Safe-tier mutation stage of the pythonista pipeline: runs real, off-the-shelf tools -- never a
bespoke analyzer -- in a detect -> fix -> rerun loop, then reports whatever those tools can't fix
themselves. No judgment calls; every finding here is something `ruff`, `mypy`, `detect-secrets`,
or `pip-audit` itself decided.

## When to Use This Skill

- The `patterns` -> `quality-tools` stage of `python-workflow`'s `tidy` or `ship-it` recipes
- Directly, whenever the user asks to lint, format, type-check, scan for secrets, or audit
  dependencies in Python code
- After `python-patterns` in a mutating pipeline -- idiom cleanup first, then mechanical tooling,
  since patterns changes can themselves introduce or resolve lint findings

## What it runs

`scripts/quality_loop.py <path>` runs five stages against `<path>`, in order:

| Stage | Tool | Behavior |
|---|---|---|
| Format | `ruff format` | Single pass, idempotent -- reformats in place |
| Lint | `ruff check --fix` | Looped: recount issues after each `--fix` pass, stop at 0 or when the count stops dropping |
| Types | `mypy` | Detect-only, no `--fix` -- every error is reported, never applied |
| Secrets | `detect-secrets scan` | Detect-only -- a real hit is never auto-remediated |
| Dependencies | `pip-audit` | Detect-only -- resolves the project root's lockfile/requirements, reports known CVEs |

Each stage runs standalone too: `--skip format,lint,types,secrets,deps` (comma-separated) drops
any subset. `--format json` for machine consumption, `--format text` (default) for a human
summary, `--max-iterations` (default 5) caps the lint loop, `--output <file>` writes instead of
printing.

## Bootstrapping

Every tool invocation goes through `uvx <tool> ...`, never a bare `<tool> ...`. `uvx` downloads
and caches the tool on first use with no separate install step -- this is the entire bootstrap
mechanism. The only hard requirement is `uv` itself on `PATH`; if it's missing, the script reports
that plainly and stops rather than trying to install a package manager.

If the target project has its own `[tool.mypy]` / `mypy.ini` config, `type_check` finds it and
defers to it. Only when no config exists does it fall back to `--ignore-missing-imports`, so a
scratch or dirty target isn't drowned in unrelated import-resolution noise.

Dependency audit resolves the project root by walking up from `<path>` for a `pyproject.toml` or
`requirements.txt` (bounded by the nearest `.git`). A `uv.lock` there is exported to a
requirements list and piped into `pip-audit`; otherwise `pip-audit` reads `requirements.txt`
directly, or falls back to auditing the current environment. No manifest found -> the stage is
reported as skipped, not failed.

## What's deliberately not here

- **Bespoke analyzers** (complexity, dead code, duplication, coupling, docstring/type-hint
  coverage, unpythonic patterns) -- that's `python-scan`'s job; this skill never re-implements an
  AST walk that a real tool already covers.
- **Idiom-level judgment** (EAFP vs LBYL, guard clauses, dataclasses vs dicts) -- `python-patterns`.
- **The five ruff-coverable anti-patterns as prose** (mutable defaults / `type()` comparisons /
  `==None` / bare `except` / `import *`) and **import ordering** -- these map directly to ruff
  rules (`B006`, `E721`, `E711`, `E722`, `F403`, `I001`) and are enforced here, not described
  anywhere else in the marketplace. `python-patterns` and `python-refactor` both route here
  instead of duplicating them as prose.

## Convergence and unresolved reporting

The lint loop's `issue_count_history` records the issue count at the start of every iteration.
`converged` is true when the count hits zero, or when a `--fix` pass produces no further drop --
that plateau means the remaining issues are real findings `ruff --fix` cannot resolve on its own
(the ones needing a semantic decision: a mutable default needs a `None` sentinel and a body edit,
a bare `except` needs a real exception type chosen). Every remaining ruff issue, every mypy error,
every secret hit, and every vulnerable dependency lands in the `unresolved` list -- that list is
what a human (or the calling `python-workflow` checkpoint) needs to look at. A secret or a CVE is
never something this skill decides how to fix; it only ever reports one.

## Explicit boundaries

- Never invokes a tool directly by name -- always through `uvx`, so no host machine needs any of
  these tools pre-installed.
- Never attempts to fix a secret finding or a dependency vulnerability -- both are detect-only,
  always reported, never mutated.
- Never proposed as skippable by `python-workflow`'s plan checkpoint -- there is no scan evidence
  that proves ruff/mypy have nothing to do (see `python-scan`'s own boundary note on this).
