---
name: python-architecture
description: >
  Whole-module structural critique using deep-module design vocabulary: is a
  module's interface small relative to what it hides (deep) or nearly as
  complex as its implementation (shallow), does it survive the deletion test,
  and does its seam sit in the right place. Emits structured findings, never
  an HTML report or a mutation. Explicit call only, or reachable through
  python-workflow's critique recipe recommending it by name.
disable-model-invocation: true
---

# Python Architecture

Whole-module/codebase structural critique: harvests `mattpocock/codebase-design`'s deletion test
and module/interface/seam vocabulary (see `references/vocabulary.md`), drops everything else
that skill did (`CONTEXT.md`/ADR integration, the interactive grilling loop, the self-contained
HTML report). Read-only, always -- like `python-review`, this skill produces a report and never
edits a file or proposes running a mutating tool.

This is a different kind of work than `python-review`: a review pass finds smells and contract
violations in code as written; this skill asks whether the *shape* of a module -- its interface
relative to its implementation, where its seam sits -- is earning its keep. Different cost,
different scope, which is why it stays its own skill rather than a third `python-review` lens.

## When to Use This Skill

- Explicit call by name, against a finished script or module -- this skill's primary target,
  not a whole live repository with its own architecture-decision trail
- Reachable through `python-workflow`'s `critique` recipe, which may end its report with a
  one-line recommendation to run this skill (see that skill's `SKILL.md`) -- `critique` only
  recommends it, it never invokes it
- **Never** auto-triggered (`disable-model-invocation: true`) and **not** one of `ship-it`'s
  "elect deep work" options -- that checkpoint only covers `python-testing-patterns`,
  `python-refactor`, and `python-performance-optimization`

## Workflow

1. **Scope.** Use the path the user named. If reached through `critique`'s recommendation and no
   path was given, ask which module to audit -- this skill never infers a target from commit
   history or "hot spots" on its own.
2. **Read the target directly.** Read every file in scope yourself -- no `Explore`-subagent
   dispatch, no commit-history walk, no `CONTEXT.md` lookup. The target is a finished module, not
   a sprawling codebase; a direct read is enough, and keeps this a single-session, no-fan-out
   skill like `python-refactor` and `python-testing-patterns`.
3. **Apply the vocabulary from `references/vocabulary.md`** to every module, class, or
   significant function in scope:
   - **Depth** -- is the interface small relative to what it hides, or nearly as complex as the
     implementation (shallow)?
   - **The deletion test** -- imagine deleting it. Complexity vanishes -> pass-through, flag it.
     Complexity reappears across callers -> earning its keep, don't flag it.
   - **Seam placement** -- does the module's interface live where callers would actually want to
     substitute behavior, or somewhere accidental?
   - **Adapter count** -- is a seam justified by >= 2 real adapters today, or hypothetical (one
     adapter, nothing yet varies across it)?
4. **Produce structured findings** -- see Report format below. No HTML file, no browser, no
   `CONTEXT.md` write, no ADR check, no interactive grilling loop.

## Report format

One entry per module/seam concern, most significant first:

```
### <module or function name> -- <Strong | Worth exploring | Speculative>
- Location: <file:line-range>
- Shape: deep | shallow (one line: why)
- Deletion test: what happens if this is deleted -- vanishes, or reappears elsewhere?
- Recommendation: plain-English description of the change, not a diff or an implementation plan
```

- **Strong** -- fails the deletion test outright (pure pass-through) or the seam is placed
  somewhere no caller can use.
- **Worth exploring** -- shallow, but not clearly a pass-through; worth a second look.
- **Speculative** -- a seam that exists for one adapter only; flag it, don't insist on it.

End with one line: total findings by strength. If nothing in scope is shallow, say so plainly --
"no deletion-test failures found" is a valid, complete result, not a reason to invent a finding.

## What's deliberately not here (routing)

| Content | Routes to | Why |
|---|---|---|
| *How* to execute a structural change (Extract Method, Encapsulate Global State, DI) | `python-refactor` | This skill identifies *that* a seam/interface should change, never the mechanics of the change itself |
| Idiom-level cleanup (EAFP, guard clauses, comprehensions) | `python-patterns` | Not a shape-of-the-interface question |
| `CONTEXT.md`/ADR reading or writing | *(dropped)* | This repo has neither; requiring them would make this skill unreachable on its own primary target (a standalone script or module) |
| The interactive grilling decision tree, the self-contained HTML/Tailwind/Mermaid report | *(dropped)* | `improve-codebase-architecture`'s HTML output can't be consumed by `critique`'s report stage -- this plugin's modularity rule requires structured output between skills, never prose or a browser report. That's the reason this skill exists at all, not a missing `CONTEXT.md` (the original justification for owning this skill was checked against the source and found false: the soft dependency creates `CONTEXT.md` lazily, it doesn't skip) |
| Deepening a cluster's internal seams, designing an interface twice via parallel sub-agents | *(dropped -- not harvested)* | Scoped harvest is the deletion test and the module/interface/seam glossary only; `codebase-design`'s `DEEPENING.md`/`DESIGN-IT-TWICE.md` content wasn't part of this skill's build scope |

## Explicit boundaries

- Never mutates a file, never proposes running a mutating tool -- structured findings only, same
  discipline as `python-review`.
- Never requires or reads `CONTEXT.md` or `docs/adr/` -- dropped from the harvest.
- Never writes an HTML file, never opens a browser, never runs the interactive grilling loop.
- Never picks the target module itself from commit history when reached through `critique`'s
  recommendation with no path given -- asks instead.
- `disable-model-invocation: true` -- explicit call only, or reachable via `python-workflow`'s
  `critique` recipe recommending it by name. Never auto-triggered, and never part of `ship-it`'s
  "elect deep work" checkpoint.

## Reference file

`references/vocabulary.md` -- the full glossary, the deep-vs-shallow diagram, and the three
principles this skill applies (the deletion test, "the interface is the test surface," "one
adapter = hypothetical, two = real").
