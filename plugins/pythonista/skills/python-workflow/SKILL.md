---
name: python-workflow
description: Run a read-only, evidence-based critique of Python code — deterministic scan (complexity, documentation coverage, dead code, duplication, code smells, unpythonic patterns) summarized into one report. Use for a health check, a review baseline, or "what's wrong with this code" before deciding what to fix. Never mutates anything.
---

# Python Workflow

Orchestrator for the pythonista pipeline. One skill, a recipe argument selects what runs. **No argument runs `critique`** — the only recipe implemented so far, and the only one this skill's description advertises. `tidy` and `ship-it` are reserved names for a later revision; do not improvise them.

## Recipes

| Recipe | Status |
|---|---|
| `critique` | Implemented (this revision): `scan -> report`, read-only, zero checkpoints |
| `tidy` | Not yet implemented — do not attempt |
| `ship-it` | Not yet implemented — do not attempt |

If asked for `tidy` or `ship-it`, say plainly that they aren't built yet rather than approximating them by running `critique` and then mutating code on your own initiative.

## `critique` — scan -> report

1. Run `python-scan`'s entry point against the target path (path relative to this skill's own directory — resolve it from wherever this skill was loaded):
   `../python-scan/scripts/analyze_all.py <path> --format json`
2. Run it again with `--format text` (or reformat the JSON output yourself) to produce the reader-facing report: severity breakdown, category breakdown, and the highest-severity findings with `file:line`.
3. Present the report to the user. Do not propose fixes, do not edit any file, and never pass `--output` to the scan — this recipe writes zero files, always.

A later revision adds a `review` stage between scan and report (`python-review`, once it exists) and a report line recommending `python-architecture` by name for whole-module structural concerns (once it exists). Neither skill exists yet — `critique` today is exactly `scan -> report`, nothing else.

## Explicit boundaries

- Never select `tidy` or `ship-it` unless the user names the recipe explicitly, by that name.
- `critique` never writes a file, never edits code, and never runs a mutating tool. If a scan analyzer can't run (a missing dependency like `radon`/`complexipy`), report that category as unavailable rather than trying to install anything.
