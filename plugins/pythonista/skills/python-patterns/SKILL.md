---
name: python-patterns
description: Apply idiomatic, behavior-preserving Python patterns -- EAFP, guard clauses, comprehensions, dataclasses, decorators, exception hierarchies, YAGNI-driven simplification -- to a file or module without changing what it does. Use when the user asks to simplify, make more idiomatic/pythonic, clean up, or reduce over-engineering in Python code, or as the idiom-cleanup stage of a mutating pipeline.
---

# Python Patterns

Safe-tier mutation stage of the pythonista pipeline: idiom-level, behavior-preserving cleanup.
Absorbs the retired `python-simplifier` skill wholesale (idioms, dead-code judgment, duplication,
YAGNI are one cognitive operation, not four) plus a verified, citation-backed cherry-pick from
`affaan-m/everything-claude-code`'s `python-patterns`.

## When to Use This Skill

- The `patterns` stage of `python-workflow`'s `tidy` or `ship-it` recipes
- Directly, whenever the user asks to simplify, "make this more pythonic", clean up naming, or
  reduce over-engineering
- Lowest-regression-risk cleanup -- reach here before `python-refactor`'s structural moves

## Workflow

1. Read `references/idioms.md` for the full before/after catalog.
2. Apply patterns incrementally, one change at a time -- never mix multiple idiom swaps in a
   single edit (see Simplification Principles in the reference).
3. Every change must be behavior-preserving. If a target project has tests, they must stay green
   after each change; if it doesn't, say so rather than claiming behavior is verified.
4. Prefer `python-scan`'s evidence (`find_dead_code`, `find_duplicates`, `find_unpythonic`,
   `find_overengineering`) to target real findings over combing files blind.

## What's in `references/idioms.md`

- Simplification Principles, EAFP vs. LBYL
- Before/after catalog: Extract and Name, Guard Clauses, Comprehensions, Dictionary Techniques,
  Context Managers
- Over-Engineering anti-patterns, When NOT to simplify
- Type hints (modern syntax, TypeVar, Protocol), dataclasses/NamedTuple, decorators,
  `__slots__`/generator idioms, exception chaining, Custom Exception Hierarchy
- Quick-reference table

## What's deliberately not here (routing)

| Content | Routes to | Why |
|---|---|---|
| Anti-Patterns table (mutable defaults, `type()`/`isinstance`, `==None`, bare `except`, `import *`) | `python-quality-tools` | All five map to real ruff rules (`B006`, `E721`, `E711`, `E722`, `F403`) -- enforced there, not duplicated as prose here |
| Import Conventions (stdlib/third-party/local ordering) | `python-quality-tools` | `ruff` `I001` territory, not a judgment call |
| Concurrency (threading/multiprocessing/async) | *(out of scope)* | High-stakes correctness territory, not an everyday idiom pass -- the one genuinely arguable routing call here, not clean-cut like the rest |
| Structural moves (Extract Method, Encapsulate Global State, DI) | `python-refactor` | Idiom-level vs. structural is the tier boundary between these two skills |

## Escalation path

`python-patterns` (this skill, idiom-level) → `python-refactor` (structural). If a cleanup needs
more than a same-function idiom swap -- splitting a function, eliminating a global, introducing a
domain model -- stop and hand off rather than forcing it through this skill's before/after catalog.

## Explicit boundaries

- Behavior-preserving only -- never changes what the code does, only how it's expressed.
- Never touches the five ruff-coverable anti-patterns or import ordering -- see routing table.
- Never mixes multiple idiom changes into one edit.
- Never proposed as skippable by `python-workflow`'s plan checkpoint unless `python-scan`'s
  `find_dead_code`, `find_duplicates`, `find_unpythonic`, and `find_overengineering` are all
  empty.
