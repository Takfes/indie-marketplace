---
name: python-workflow
description: Run the pythonista pipeline against Python code via one of three recipes — critique (read-only scan -> report, the default with no recipe named), tidy (safe-tier mutation: scan -> patterns -> quality-tools -> verify, with an approval checkpoint before any write), or ship-it (scan -> document -> patterns -> quality-tools -> optional deep work -> verify -> commit). Use for a health check or review baseline (critique), a low-risk cleanup pass (tidy), or a full mutate-and-commit pass (ship-it). With no recipe named, always run critique — only run tidy or ship-it when the user names that recipe explicitly.
---

# Python Workflow

Orchestrator for the pythonista pipeline. One skill, a recipe argument selects what runs.

## Recipes

| Recipe | Pipeline |
|---|---|
| `critique` (default) | `scan -> report` — read-only, zero checkpoints |
| `tidy` | `scan -> [approve plan] -> patterns -> quality-tools -> verify -> [approve terminal act]` |
| `ship-it` | `scan -> [approve plan] -> document -> patterns -> quality-tools -> [elect deep work] -> verify -> [approve commit] -> git-commit` |

**No recipe argument runs `critique`.** Never select `tidy` or `ship-it` unless the user names that recipe explicitly, by that name — do not infer either from phrases like "clean this up" alone.

`tidy` and `ship-it` hand off to `python-document`, `python-patterns`, and `python-quality-tools` by name. None of the three exist yet in this marketplace (tracked separately). Until they ship, running either recipe past the plan checkpoint will fail to find those skills — say so plainly and stop rather than improvising their behavior yourself.

## `critique` — scan -> report

1. Run `python-scan`'s entry point against the target path (path relative to this skill's own directory — resolve it from wherever this skill was loaded):
   `../python-scan/scripts/analyze_all.py <path> --format json`
2. Run it again with `--format text` (or reformat the JSON output yourself) to produce the reader-facing report: severity breakdown, category breakdown, and the highest-severity findings with `file:line`.
3. Present the report to the user. Do not propose fixes, do not edit any file, and never pass `--output` to the scan — this recipe writes zero files, always.

A later revision adds a `review` stage between scan and report (`python-review`, once it exists) and a report line recommending `python-architecture` by name for whole-module structural concerns (once it exists). Neither skill exists yet — `critique` today is exactly `scan -> report`, nothing else.

## Checkpoints

Both `tidy` and `ship-it` use these; each decides something real, none is a formality to click through.

### 1. Approve the plan

After the scan, before any write. Using the scan evidence, propose which stages will run and which the evidence says can be skipped — present this as a plan, not a silent decision:

| Stage | Skip proposed when | Evidence source |
|---|---|---|
| `python-document` | docstring coverage >=80% and type-hint coverage >=90% | `check_documentation.py` |
| `python-patterns` | `find_dead_code`, `find_duplicates`, `find_unpythonic`, `find_overengineering` all empty | those four analyzers |
| `python-quality-tools` | never — no `python-scan` analyzer produces ruff/mypy evidence | — |

Wait for the user to approve, adjust, or reject the plan before running any stage that writes.

### 2. Elect deep work (`ship-it` only)

After the safe tier (`document` -> `patterns` -> `quality-tools`), before `verify`. Ask explicitly whether to hand off to `python-testing-patterns`, `python-refactor`, and/or `python-performance-optimization` — attach the scan evidence relevant to each. Only enter a deep-work stage with the user's explicit consent given at this checkpoint; approving the plan in step 1 is not consent for this. No answer or "no" means skip straight to `verify`.

### 3. Approve the terminal act

- **`ship-it`**: draft a Conventional Commits message from the accumulated diff, present the diff and the message, and do not invoke `git-commit` until approved.
- **`tidy`**: there is no commit. Mutations from `patterns`/`quality-tools` (and any deep-work stage) are already applied to the working tree as they run — this checkpoint presents the full diff since the scan and asks the user to keep or revert it. Never leave uncommitted mutations without asking.

## `tidy` — scan -> patterns -> quality-tools -> verify

1. Run the scan: `../python-scan/scripts/analyze_all.py <path> --format json` (same entry point as `critique`).
2. **Checkpoint: approve the plan** (see above). `python-quality-tools` is never proposed as skippable.
3. Run the approved stages in order, applied directly to the working tree: `python-patterns` against `<path>` (skip if approved), then `python-quality-tools` against `<path>`.
4. **Verify.** Re-run the scan and diff it against the step-1 baseline to confirm the mutated stages' evidence improved, or at least didn't regress. If the target has a discoverable test suite, run it and report pass/fail. If it doesn't, say so explicitly rather than claiming behavior is verified.
5. **Checkpoint: approve the terminal act** (see above). `tidy` never commits — that's `ship-it`'s job.

## `ship-it` — scan -> document -> patterns -> quality-tools -> [deep work] -> verify -> git-commit

1. Run the scan: same entry point as above.
2. **Checkpoint: approve the plan** (see above), including `python-document`.
3. Run the approved safe-tier stages in order, applied directly to the working tree: `python-document` -> `python-patterns` -> `python-quality-tools`.
4. **Checkpoint: elect deep work** (see above).
5. Run any elected deep-work stage(s), attaching the relevant scan evidence to each.
6. **Verify.** Same as `tidy`'s verify step: re-run the scan and diff against the step-1 baseline, run the test suite if one exists, report unresolved gaps plainly.
7. **Checkpoint: approve the commit** (see above).
8. **Soft-dependency probe.** Before invoking, confirm the `git-commit` skill (from the `codementor` plugin) is actually available in this session. If it isn't, don't fail the recipe: tell the user it's unavailable, then either present the drafted Conventional Commits message and `git commit` command for them to run themselves, or run `git commit` directly with that message if the user asks you to. Never silently skip the commit and never silently substitute a different commit workflow without saying so.

## Explicit boundaries

- Never select `tidy` or `ship-it` unless the user names the recipe explicitly, by that name. With no argument, always run `critique`.
- `critique` never writes a file, never edits code, and never runs a mutating tool.
- `tidy` and `ship-it` never run a mutating stage before the plan checkpoint is approved. `ship-it` never enters a deep-work stage without explicit consent at the "elect deep work" checkpoint.
- `ship-it` never invokes `git-commit` before the commit checkpoint is approved, and never fails the whole recipe just because `git-commit` is unavailable — degrade per the soft-dependency probe above instead.
- `python-quality-tools` is never proposed as skippable, in either recipe.
- If a scan analyzer can't run (a missing dependency like `radon`/`complexipy`), report that category as unavailable rather than trying to install anything.
