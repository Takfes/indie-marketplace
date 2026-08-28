# Pythonista plugin plan — v2 draft

**Status: draft, under active discussion.** Supersedes `pythonista-plugin-plan.md` where the
two disagree; produced by re-deriving the design from first principles rather than accepting
that plan's settled-decisions table as fixed. Written for an adversarial review pass — open
items are marked explicitly rather than silently resolved.

Inputs: `pythonista-plugin-design-chatgpt.md`, `pythonista-plugin-design-claude.md`, and
`pythonista-plugin-plan.md` (the prior synthesis of the first two), all in this same `docs/`
directory. This document treats all three as raw input of equal standing, not as settled fact.

## Framing (unchanged from the prior plan)

Not "build a pipeline." In order: identify the capabilities actually needed → modularize them
so each has one job and no overlap → place them (script vs. skill vs. recipe) → recompose a
few into named workflows. There is no single true pipeline, only atomic capabilities and a few
legitimate compositions of them.

**Modularity test applied to every skill below:** can you state in one line what it does, how
you invoke it, and what it depends on? Where one skill's output feeds another, that output is
structured (JSON, `FILE:LINE` findings) — never prose requiring a second interpretation pass.

## Layer model

```
Layer 2   Recipes         critique · tidy · ship-it        (compositions, one skill + 3 args)
Layer 1   Capabilities    one job each, independently invocable
Layer 0   Analysis        shared deterministic scripts, no judgment
```

## Skill inventory — 12 skills

Net change from the prior plan's 11: **+1, `python-architecture`**, replacing a soft
cross-plugin dependency with an owned skill (reasoning below). This is the one inventory-level
change in this draft and is flagged as an open item for explicit sign-off.

| # | Skill | Job | Mutates? | Pipeline role |
|---|---|---|---|---|
| 1 | `python-scan` | Read-only deterministic analyzers → structured JSON (complexity, dedup, dead code, coupling, docstring/type coverage, overengineering, unpythonic constructs) | No | Evidence for every other stage; gates whether a stage runs at all |
| 2 | `python-review` | Judgment critique of a module or diff — prioritized findings, each with `FILE:LINE` evidence, gated by a false-positive/suppression check before anything ships | No | `critique` recipe only |
| 3 | `python-patterns` | Idioms, dead code, duplication, YAGNI — behavior-preserving | Yes, safe tier | `tidy`, `ship-it` |
| 4 | `python-document` | Module summaries, docstrings, type annotations, comments — additive only | Yes, safe tier | `ship-it` |
| 5 | `python-quality-tools` | ruff format/check --fix, mypy, secret scan, dep audit — detect→fix→rerun loop | Yes, safe tier | `tidy`, `ship-it` |
| 6 | **`python-architecture`** *(new)* | Whole-module/codebase structural critique: seams, adapters, the deletion test, module/interface vocabulary | No | `critique`'s optional deep lane |
| 7 | `python-refactor` | Structural moves only: Extract Method, Encapsulate Global State, Group Related Functions, Create Domain Models, DI. Idiom-level entries removed — link to `python-patterns` instead | Yes, structural tier | Deep work, explicit call only |
| 8 | `python-testing-patterns` ✅ | Tests-after workflow: plan seams → confirm ambiguity with user → write one seam at a time → prove non-trivial tests can fail → flag testability smells | Yes (adds tests) | Deep work, explicit call only |
| 9 | `python-performance-optimization` ✅ | Evidence-first profiling: hotspot report or live dashboard | No (profiling only; optimization is a separate explicit step) | Deep work, explicit call only |
| 10 | `python-packaging` | Distribution shape: src/flat layout, pyproject.toml, build backend, PyPI publishing | Yes | Deep work, explicit call, unchanged from community |
| 11 | `uv-package-manager` | `uv` CLI reference: deps, venvs, Python versions, lockfiles | Yes | Deep work/utility, explicit call, unchanged |
| 12 | `python-workflow` | Orchestrator. One skill, three recipe args (`critique`/`tidy`/`ship-it`). No expertise of its own — checkpoints, soft-dep probing, evidence-conditioned stage-skip logic | — | Is the pipeline |

### Why these boundaries survive independent scrutiny (not just inherited)

- **`python-scan` stays separate from `python-quality-tools`**, rejecting the prior plan's own
  trim option. Not just an output-shape difference: `python-scan`'s analyzers (complexity,
  dedup, coupling) have no `--fix` mode — a human/LLM has to *decide* what to do with a
  complexity score. `python-quality-tools`'s checks (ruff, mypy, secret-scan) are directly
  actionable by the same tool that found them. Merging would blur the mutate/no-mutate line the
  whole checkpoint design depends on.
- **`python-patterns` absorbs `python-simplifier` wholesale** — confirmed. Idioms, dead code,
  duplication, and YAGNI are one cognitive operation (assess code against a quality bar), not
  four. Splitting them buys no real boundary.
- **Self-contained Python, no agnostic core** — confirmed. A generic core only pays for itself
  with ≥2 language packs consuming it; there is one today. Building it now is the
  "configurability that wasn't requested" this project's own conventions warn against.
- **`python-workflow` is one skill with recipe args, not three skills.** The shared machinery —
  checkpoint UI, soft-dep probing, "establish state" — is real, load-bearing duplication if
  split, unlike the scan/quality-tools case where the apparent overlap was superficial.

## Recipes — pipeline vs. ad-hoc

**In the pipeline** (`python-workflow <recipe>`):

```
critique:  scan → review → report                          [read-only, 0 checkpoints]
                     └─optional─▶ python-architecture

tidy:      scan → 🛑 approve plan → patterns → quality-tools → verify → 🛑 diff review

ship-it:   scan → 🛑 approve plan → document → patterns → quality-tools
                → 🛑 approve consequential work → verify → 🛑 approve commit → git-commit
```

**Ad-hoc — explicit call only, never auto-triggered** (a checkpoint may *recommend*, only the
user *starts*): `python-testing-patterns`, `python-refactor`, `python-performance-optimization`,
`python-architecture`, `python-packaging`, `uv-package-manager`.

**Checkpoints: three, unchanged from the prior plan, re-derived independently and held.**
1. Approve the plan — after evidence, before any write.
2. Approve consequential work — before anything structural, behavior-changing, or expensive.
3. Approve the commit — the only irreversible act.
Five is checkpoint fatigue; two lets judgment-based edits land unreviewed; three is the
read→write and reversible→irreversible boundary.

**New in this draft, not present in either source doc or the prior plan: evidence-conditioned
execution.** Recipe stages consult `python-scan`'s findings before running and skip a stage
with nothing to act on (e.g., don't invoke `python-document` if docstring coverage is already
100%), reported as "skipped — nothing to do" rather than run for zero effect. Same
evidence-over-ritual logic the prior plan already used to reject code-review-as-steering,
applied one level deeper into the recipes themselves.

## Cherry-pick findings (grounded in the actual source files, not the prior plan's placeholder attributions)

### `python-review` ← mattpocock/code-review + codementor/code-review-excellence + beagle/python-code-review

| Source | Keep | Skip |
|---|---|---|
| mattpocock/code-review | Two-axis Standards/Spec report shape; parallel sub-agent dispatch so axes don't pollute each other; 12-smell Fowler baseline, each with a fix hint; "repo standard overrides baseline" rule | The diff-fixed-point mechanism as the *only* mode — must also run against a standalone finished module |
| codementor/code-review-excellence | Severity taxonomy (blocking/important/nit/suggestion/learning/praise) | All interpersonal/mentoring content — zero agentic value; propose retiring it from `codementor` once harvested |
| beagle/python-code-review | The actual prize: Scope → false-positive screen → Evidence (`FILE:LINE` mandatory) → Verification → Ship gate — the one mechanism here that directly fixes LLM-reviewer hallucination/noise | Its Python taxonomy (PEP8/type-safety/async/error-handling) — mechanical, ruff/mypy-coverable, routed to `python-quality-tools` instead |

Spine: mattpocock's two-axis skeleton + smell baseline → codementor's severity labels as
presentation → beagle's gate as a hard pre-output check.

### `python-patterns` ← affaan-m/python-patterns + python-simplifier prose

| Source | Keep | Skip |
|---|---|---|
| python-simplifier (prose) | The spine, not a donor: Simplification Principles, before/after catalog (Extract-and-Name, Early Returns, Comprehensions, Dictionary Techniques, Context Managers), Over-Engineering anti-patterns, "when NOT to simplify" | — |
| affaan-m/python-patterns | Idiom categories simplifier lacks: EAFP vs. LBYL, type-hint depth, dataclasses/NamedTuple, decorators, `__slots__`/generator memory idioms | Concurrency section → `python-performance-optimization`'s territory; package-layout/tooling → `python-packaging`'s territory; its Anti-Patterns table is ruff-coverable (B006/E721/E711) → route to `python-quality-tools`'s ruleset, don't duplicate as prose |
| beagle | (fully claimed by `python-review`) | Nothing — its checklist duplicates affaan-m's Anti-Patterns near line-for-line; taking both reproduces the collision |

**Second prose duplication the prior plan missed:** `python-simplifier`'s "Early Returns" /
"Dictionary Techniques" overlap `python-refactor`'s catalog entries "Guard Clauses" /
"Dictionary Dispatch." Fix: `python-patterns` owns the idiom-level version; `python-refactor`'s
catalog links out instead of re-describing, keeping its own catalog to genuinely structural
moves.

### `python-scan` ← python-simplifier/scripts/ + python-refactor/scripts/

Ships **~7 analyzers, not "8+7 deduped."**

| Script | Source | What it does | Verdict |
|---|---|---|---|
| `analyze_multi_metrics.py` | refactor | cognitive + cyclomatic + maintainability index | **Winner** for complexity |
| `analyze_complexity.py` | simplifier | bespoke AST cyclomatic-only | Retire — superseded |
| `measure_complexity.py` | refactor | bespoke cyclomatic+length AST walk | **Retire — a second duplicate**, within refactor's own set, missed by the prior plan |
| `analyze_with_flake8.py` + `compare_flake8_reports.py` | refactor | shell out to flake8 + 8 plugins | **Retire outright.** Refactor's own SKILL.md already declares ruff the primary stack |
| `check_documentation.py` | refactor | docstring + type-hint coverage | Keep — unique |
| `find_duplicates.py`, `find_dead_code.py`, `find_coupling_issues.py`, `find_overengineering.py`, `find_unpythonic.py` | simplifier | each unique, no counterpart | Keep all five |
| `find_code_smells.py` | simplifier | grab-bag, unlabeled | Undetermined — read closer at build time, fold overlaps into the winners above |
| `analyze_all.py`, `compare_metrics.py`, `benchmark_changes.py` | both | orchestrator / before-after comparison harness | **Not Layer-0 material** — this is `python-refactor`'s own regression-prevention job; stays there |

Bonus: refactor's metric-threshold table (cyclomatic <10/warn 15/err 20, cognitive <15/warn 20,
docstring >80%, type-hint >90%) is already tuned — use it as `python-scan`'s pass/warn/fail
bands instead of inventing new ones.

### `python-testing-patterns` (already shipped) — gap check, not a redo

No real gap: mattpocock's seam-confirm-with-user workflow and superpowers' "prove it can fail"
discipline don't transfer cleanly beyond what's already there, because this skill is
deliberately tests-*after*, not TDD-loop. One cheap addition worth taking: mattpocock's
sharper one-line tautological-test definition ("expected value must come from a source
independent of the code's own computation").

## `python-architecture` — the one inventory change, and why (needs sign-off)

The prior plan kept `improve-codebase-architecture` as a soft cross-plugin dependency
(mattpocock/codebase-design + domain-modeling + essentials/grilling). Researching what each
dependency actually contributes:

| Dependency | Concrete contribution |
|---|---|
| codebase-design | The actual analysis engine — module/interface/depth/seam vocabulary, the deletion test, "one adapter = hypothetical seam, two = real" |
| domain-modeling | CONTEXT.md/ADR glossary upkeep — near-zero value without an existing CONTEXT.md in the target repo |
| grilling | The frontier/rounds interview mechanic for walking a candidate |

Only `codebase-design` is load-bearing. This plugin's primary use case is a **finished script or
module**, not a repo with existing architecture-decision discipline — so the soft-dependency
would degrade-and-skip most of the times it's actually invoked, which defeats offering it as a
deep lane at all.

**Proposal:** author `python-architecture` as an owned skill, harvesting only `codebase-design`'s
deletion test and module/interface/seam vocabulary, dropping the CONTEXT.md/ADR requirement and
the `grilling` dependency. Side effect: removes the last cross-plugin coupling in this plugin
except `git-commit`.

`git-commit` is kept as a soft reference, not owned, and deliberately treated differently: it's
a single skill with no precondition chain (unlike the three-plugin architecture chain), and
it's genuinely reusable if a second language pack is ever added — the compound-dependency
problem that broke the `improve-codebase-architecture` soft-dep doesn't apply here.
`git-commit` lives in the `codementor` plugin, whose own stated purpose is "git workflow and
code review hygiene skills" (alongside `git-cleanup`, `code-review-excellence`) — that is
already the right home, not an accident, and moving it to `essentials` would fight the
plugin's own reason for existing. No change proposed.

## Subagent profiles (new — proposal, not yet built)

This repo already has one clean example of the intended house style —
`plugins/codex/agents/codex-rescue.md`: minimal frontmatter (`name`, `description`, `model`,
`tools`, `skills`), a tight single-purpose prompt, explicit "do not" boundaries, no fabricated
"Communication Protocol" JSON stubs, no references to agents/tools that don't exist in this
marketplace. That is the template to follow — not the generic wshobson/agents-style mega-prompt
agents (verbose checklists, fake integration sections naming nonexistent collaborator agents).

Grounded in the dispatch model already settled in the source docs ("sequential pipeline;
fan-out only for independent read-only analysis"), two profiles are justified — no more:

1. **`python-review-lens`** — runs one axis (Standards or Spec) of `python-review`'s two-axis
   analysis. Read-only: `Read, Grep, Glob, Bash`. Dispatched twice in parallel by `python-review`
   itself so the axes don't pollute each other (this is literally what mattpocock/code-review's
   own design calls for). Model: `sonnet` by default; caller may request `opus` for a
   high-stakes review.
2. **`python-performance-profiler`** — runs a profiling job (`profile_report.py` /
   `live_dashboard.py`) in isolation so a long-running, verbose profiling pass doesn't pollute
   the main session's context. Tools: `Bash, Read`. Model: `sonnet` — mechanical execution, no
   deep judgment required.

No profile proposed for `python-architecture`, `python-refactor`, or `python-testing-patterns` —
these are explicit-call, single-session, deep-work skills with no fan-out need; adding a profile
for them would be unrequested configurability.

**Mechanism note:** `build.py` currently has no `agents:` block (confirmed by inspection) — only
`plugins/codex/agents/` exists, vendored whole via the `vendor:` mechanism, not generated. Adding
local agent profiles to `pythonista` means hand-authoring `skills/../agents/*.md` (or wherever
this repo's convention lands) the same way local skills are hand-authored, not a new build.py
capability — no build-mechanism change needed for two static files.

## Open items requiring explicit sign-off

1. **`python-architecture` as owned skill (12 vs. 11 total)** — see above. Reversible if
   rejected: fall back to the prior plan's soft-dependency reference.
2. **CLI-invocation-design gap in `python-packaging`** — flagged during Q&A: nothing currently
   covers designing the CLI surface itself (argument ergonomics), only wiring `[project.scripts]`
   entry points. Fold into this pass, or leave flagged for later?
3. **Workflow-discipline gap in `python-performance-optimization`** — it reads as a reference
   manual (excellent scripts, profiler-choice table, pitfalls list) rather than a disciplined
   workflow with an enforced gate, unlike `python-testing-patterns`'s explicit numbered
   "Workflow" section. Missing: an enforced baseline → prove-there's-a-problem → profile →
   propose → 🛑 approve → optimize → re-benchmark → compare sequence (this is literally what
   the chatgpt source doc asked for — "Its first question should effectively be: 'Where is the
   evidence that this needs optimization?'" — and it's currently implied by good tooling, not
   structurally enforced). Also missing a before/after benchmark-comparison script — ironically,
   `python-refactor` already has one (`compare_metrics.py`, `benchmark_changes.py`) that could be
   ported over instead of reinvented. Fold in, or leave flagged?

## Build order (supersedes the prior plan's step 2 given the corrected script inventory)

Unchanged in shape from the prior plan, corrected in step 2's actual scope: `python-scan`
consolidates ~7 analyzers (not 8+7), with three explicit retirements (not just dedup) and two
scripts redirected to stay in `python-refactor`. `python-architecture` is a new step between the
prior plan's steps 6 and 7 (merge `python-review`) and 7 (rework `python-refactor`), harvesting
only `codebase-design`'s vocabulary. Subagent profiles are authored alongside `python-review`
(step 6, for `python-review-lens`) and `python-performance-optimization`'s revision if the
workflow-discipline item above is accepted (for `python-performance-profiler`).
