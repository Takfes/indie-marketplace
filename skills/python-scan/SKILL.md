---
name: python-scan
description: Run deterministic, read-only Python code analyzers — complexity, maintainability, documentation/type-hint coverage, code smells, over-engineering, dead code, unpythonic patterns, coupling, and duplication — and produce one structured JSON report. No judgment, no mutation. Use as the evidence baseline before any review, cleanup, or refactor pass, or to decide whether a downstream stage is even worth running.
---

# Python Scan

Layer 0 of the pythonista pipeline: deterministic analysis only, zero judgment, zero mutation. Every other skill in this plugin either reads this skill's output or produces something this skill can later re-measure.

## When to Use This Skill

- Before any review, cleanup, or refactor pass — establish the evidence baseline first
- Deciding whether a downstream stage is worth running (e.g. skip documentation work if coverage is already high)
- A quick "what's actually wrong with this file/project?" check, in CI or ad hoc

## What it runs

`scripts/analyze_all.py <path> --format json` fans out to 8 analyzers and merges the results into one report:

| Analyzer | Detects |
|---|---|
| `analyze_multi_metrics.py` | Cyclomatic + cognitive complexity, maintainability index (radon + complexipy) |
| `check_documentation.py` | Missing docstrings, missing type hints, missing module docstring |
| `find_code_smells.py` | Magic numbers, bare excepts, god classes, data classes, long parameter lists |
| `find_overengineering.py` | Unused abstractions, YAGNI violations |
| `find_dead_code.py` | Unused imports and functions |
| `find_unpythonic.py` | `range(len(x))`, `== True`, and similar non-idiomatic constructs |
| `find_coupling_issues.py` | Feature envy, message chains |
| `find_duplicates.py` | AST-based duplicate code |

Each analyzer also runs standalone: `scripts/<name>.py <path> --format json` (or `--format text` for a human-readable report). `analyze_all.py` accepts `--skip-duplicates` for large trees where duplicate detection is slow, and `--output <file>` to write the report instead of printing it.

## What's deliberately not here

- Mutable-default and `type()`-comparison checks — ruff already flags these (`B006`, `E721`); see `python-quality-tools`.
- Ruff/mypy/formatting itself — deterministic, but not this skill's job; see `python-quality-tools`.
- Judgment calls (is this actually worth fixing, what's the right fix) — see `python-review`, `python-patterns`, `python-architecture`.

## Thresholds

Pass/warn/fail bands, tuned by `python-refactor` and shared here as the marketplace-wide default:

| Metric | Pass | Warn | Fail |
|---|---|---|---|
| Cyclomatic complexity | < 10 | ≥ 15 | ≥ 20 |
| Cognitive complexity | < 15 | ≥ 20 | ≥ 25 |
| Docstring coverage (public items) | ≥ 80% | — | < 80% |
| Type-hint coverage (public params) | ≥ 90% | — | < 90% |

## Output shape

```json
{
  "meta": {"analyzed_path": "...", "timestamp": "...", "analyzers_run": ["..."]},
  "summary": {"total_issues": 0, "by_severity": {"high": 0, "medium": 0, "low": 0}, "by_category": {}},
  "categories": {"<analyzer>": {"issues": [...], "count": 0}}
}
```

Every issue carries at least `file`, `line`, `severity`, and a type field (`issue_type`, `smell_type`, or `pattern_type` depending on which analyzer produced it) — code consuming the report should fall back across those keys rather than assume one name. Running `analyze_multi_metrics.py` or `check_documentation.py` standalone (not through `analyze_all.py`) additionally returns the full per-file metrics (`files`/`coverage`, thresholds) behind the flattened issue list.

Read-only, always. Never mutates a file and never proposes a fix — that judgment belongs to every other skill downstream of this one.
