---
name: python-document
description: Add missing module summaries, docstrings, type annotations, and why-comments to Python code -- additive only, never changing behavior or rewording existing documentation. Use when the user asks to document, add docstrings/type hints/comments to, or improve documentation coverage of Python code, or as the documentation stage of a ship pipeline.
---

# Python Document

Safe-tier mutation stage of the pythonista pipeline: additive documentation only. Targets exactly
the gaps `python-scan`'s `check_documentation.py` flags -- missing module docstrings, missing
public function/class docstrings, missing type hints -- and fills them, matching whatever
docstring convention the target project already uses.

## When to Use This Skill

- The `document` stage of `python-workflow`'s `ship-it` recipe (runs first in the safe tier, before
  `patterns` and `quality-tools`)
- Directly, whenever the user asks to document code, add docstrings, add type hints, or improve
  documentation coverage

## Workflow

1. **Get evidence.** Run `../python-scan/scripts/check_documentation.py <path> --format json` (or
   use a scan report already supplied by `python-workflow`) to get exactly which modules, classes,
   and functions are missing a docstring, a return type, or parameter types -- and the
   `docstring_coverage_pct` / `type_hint_coverage_pct` baseline to compare against afterward.
2. **Detect the target project's docstring convention** before writing a single line:
   - Sample a few already-documented public functions/classes in the target project. `Args:` /
     `Returns:` / `Raises:` sections → Google style. `Parameters\n----------` → NumPy style.
     `:param x:` / `:returns:` → reST/Sphinx style.
   - Check for a documented convention: a style guide, `CONTRIBUTING.md`, or a project
     `CLAUDE.md`/`AGENTS.md`.
   - If genuinely nothing is documented or sampled, default to Google style (Args/Returns/Raises)
     -- this marketplace's own default -- and say so explicitly rather than silently picking one.
   - **The detected or existing convention always wins over the default.** Never mix styles
     within one file.
3. **Fill gaps only.** For each item `check_documentation.py` flagged:
   - Missing module docstring → one-paragraph purpose summary at the top of the file.
   - Missing function/class docstring → purpose, parameters, return value, and any exceptions the
     body can actually raise, in the detected convention.
   - Missing type hints → infer from actual usage (return statements, default values, how a
     parameter is used in the body), not guessed. Use modern syntax (`X | None`, `list[str]`) —
     check the target's `pyproject.toml` `requires-python`; only fall back to `typing.Optional`/
     `List` if it targets < 3.10.
4. **Never touch what's already there.** Don't reword an existing docstring, don't "improve" an
   existing comment, don't add a docstring's `Raises:` entry for an exception the function can't
   actually raise (that's inventing a claim, not documenting one).
5. **Verify no behavior change.** The diff should be additive-only: new docstrings, new type
   annotations, new comments. Nothing else moves. If the target has tests, run them before and
   after — they must stay identical. If it doesn't, say so explicitly rather than claiming
   behavior is verified.

## What's deliberately not here

- **Judging whether existing documentation is adequate or accurate** — that's `python-review`'s
  Contract axis (does the docstring's claim match what the body does?), not this skill's. This
  skill only fills *absence*, it doesn't audit *presence*.
- **Naming, structure, or idiom choices** — `python-patterns` / `python-refactor`.
- **Formatting the file** — `python-quality-tools`'s `ruff format` runs after this stage in
  `ship-it` and will reflow anything this skill adds.

## Explicit boundaries

- Additive only — every edit either adds a docstring, adds a type annotation, or adds a comment.
  Never edits, removes, or rewords existing documentation or code.
- Never invents a documented behavior (a `Raises:` entry, a side effect) the code doesn't actually
  have — every claim must be checkable against the body being documented.
- Never proposed as skippable by `python-workflow`'s plan checkpoint below the tuned bands
  (docstring coverage ≥80% **and** type-hint coverage ≥90%, from `check_documentation.py`) — both
  must clear the bar, not either.
