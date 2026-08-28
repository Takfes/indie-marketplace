# Pythonista plugin plan — v2

**Status: finalized.** Supersedes `pythonista-plugin-plan.md` where the
two disagree. First produced by re-deriving the design from first principles rather than
accepting that plan's settled-decisions table as fixed; then put through an independent
adversarial review (`docs/202608280959-review-pythonista-plan-v2.md`, staff-engineer persona,
opus, fresh context) that verified claims against the actual vendored source files and found
real defects, not just style nits. This revision folds in that review's remediation plan.
Verdict on the pre-review draft was **"sound with gaps"**: the layer model, recipe shape, and
merge decisions held up; enforcement did not — every safety rule was prose with no mechanism
behind it, and two cherry-pick table rows were factually wrong when checked against the actual
scripts. Both classes of problem are fixed below.

**Provenance note, resolved:** `affaan-m/everything-claude-code` and
`existential-birds/beagle` have now been independently fetched and read twice — once during
initial cherry-picking, once again as a targeted re-verification pass with citations, after the
adversarial review correctly noted no persistent evidence trail existed for either. Every claim
below attributed to them is now citation-backed (file/section references). One genuine miss
from the first pass is folded in below: beagle's evidence gate references a sibling skill,
`review-verification-protocol`, that does exist and was not read the first time — it turns out
to be the actual substance behind beagle's "prize" framing, not just a name-check. Residual gap:
beagle's `pep8-style.md`, `type-safety.md`, `async-patterns.md`, and `error-handling.md`
reference files, and affaan-m's non-English/mirror directories, remain unread — low-value, not
blocking. Neither upstream is vendored in `bundles.yaml` or the tree, correctly, per the
harvest-don't-vendor rule.

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
cross-plugin dependency with an owned skill. **Confirmed** (user sign-off, after the reviewer
corrected the original argument for it — see below) — keep it as its own skill, not folded
into a `python-review` lens: architecture audits are a different kind of work than a review
pass (different cost/scope), and discoverability is solved separately, not by bundling.

| # | Skill | Job | Mutates? | Pipeline role | Auto-invocable? |
|---|---|---|---|---|---|
| 1 | `python-scan` | Read-only deterministic analyzers → structured JSON (complexity, dedup, dead code, coupling, docstring/type coverage, overengineering, unpythonic constructs) | No | Evidence for every other stage; gates whether a stage runs at all | Yes |
| 2 | `python-review` | Judgment critique of a module or diff — prioritized findings, each with `FILE:LINE` evidence, gated by a false-positive/suppression check before anything ships | No | `critique` recipe only | Yes |
| 3 | `python-patterns` | Idioms, dead code, duplication, YAGNI — behavior-preserving | Yes, safe tier | `tidy`, `ship-it` | Yes |
| 4 | `python-document` | Module summaries, docstrings, type annotations, comments — additive only | Yes, safe tier | `ship-it` | Yes |
| 5 | `python-quality-tools` | ruff format/check --fix, mypy, secret scan, dep audit — detect→fix→rerun loop | Yes, safe tier | `tidy`, `ship-it` | Yes |
| 6 | `python-architecture` | Whole-module/codebase structural critique: seams, adapters, the deletion test, module/interface vocabulary | No | `critique`'s report *recommends* it by name (see Recipes) | **No — `disable-model-invocation: true`** |
| 7 | `python-refactor` | Structural moves only: Extract Method, Encapsulate Global State, Group Related Functions, Create Domain Models, DI. Idiom-level entries removed — link to `python-patterns` instead | Yes, structural tier | Deep work; electable at `ship-it` checkpoint 2, or explicit call | **No — `disable-model-invocation: true`** |
| 8 | `python-testing-patterns` ✅ | Tests-after workflow: plan seams → confirm ambiguity with user → write one seam at a time → prove non-trivial tests can fail → flag testability smells | Yes (adds tests) | Deep work; electable at `ship-it` checkpoint 2, or explicit call | **No — `disable-model-invocation: true`** |
| 9 | `python-performance-optimization` ✅→**revised** | Evidence-first profiling under an enforced workflow: baseline → prove there's a problem → profile → propose → 🛑 approve → optimize → re-benchmark → compare. Adds a ported benchmark-comparison script | No (profiling only; optimization is a separate, checkpointed explicit step) | Deep work; electable at `ship-it` checkpoint 2, or explicit call | **No — `disable-model-invocation: true`** |
| 10 | `python-packaging` **→revised** | Distribution shape (src/flat layout, pyproject.toml, build backend, PyPI publishing) **plus CLI surface design** (argument ergonomics, `[project.scripts]` entry-point wiring) | Yes | Deep work, explicit call | Yes (low harm, read-mostly reference) |
| 11 | `uv-package-manager` | `uv` CLI reference: deps, venvs, Python versions, lockfiles | Yes | Deep work/utility, explicit call, unchanged | Yes (low harm, read-mostly reference) |
| 12 | `python-workflow` | Orchestrator. One skill, three recipe args (`critique`/`tidy`/`ship-it`). **No argument defaults to `critique`** — `tidy`/`ship-it` require the user to name them. No expertise of its own | — | Is the pipeline | Yes, but description advertises only the read-only entry point |

### Why these boundaries survive independent scrutiny (re-verified by adversarial review)

- **`python-scan` stays separate from `python-quality-tools`**, rejecting the prior plan's own
  trim option. **Survives, with one correction:** the original framing ("analyzers have no
  `--fix` counterpart") is slightly off — `check_documentation.py`'s output *does* have a fixer,
  it's just a different skill (`python-document`) in a different tier. The real criterion:
  the fixer is always a separate, tier-appropriate skill, never the analyzer itself. Conclusion
  unchanged either way.
- **`python-patterns` absorbs `python-simplifier` wholesale** — confirmed, survives. Idioms,
  dead code, duplication, and YAGNI are one cognitive operation, not four.
- **Self-contained Python, no agnostic core** — confirmed, off-limits for this pass. The test
  ("a generic core only pays for itself with ≥2 language packs") is correct and there is one
  today.
- **`python-workflow` is one skill with recipe args, not three skills.** **Argument corrected**
  by review: the original reasoning ("shared checkpoint/probing machinery would duplicate")
  was the weaker available case — three skills could each link one shared reference file, so
  that alone doesn't force one skill. The reason that actually holds: there must be exactly one
  entry point capable of reaching `git-commit`, and one skill description for the model to
  match invocation against — which is also what makes the read-only-by-default rule below
  enforceable at all. Same conclusion, sounder argument.

## Enforcement — not prose, mechanism

The pre-review draft declared six skills "explicit call only, never auto-triggered" without
anything that actually stopped auto-invocation. This marketplace already has the primitive:
`disable-model-invocation: true` appears in 14 other SKILL.md files across the marketplace and,
before this fix, zero pythonista ones — `python-refactor`'s shipped description still triggers
on "clean this up," the exact collision this plan exists to end.

- `disable-model-invocation: true` on the four skills that mutate structurally or run expensive
  work: `python-architecture`, `python-refactor`, `python-testing-patterns`,
  `python-performance-optimization`. `python-packaging` and `uv-package-manager` stay
  auto-invocable — read-mostly references, low harm.
- `python-workflow` with **no recipe argument runs `critique`** (read-only). `tidy` and
  `ship-it` require the user to name the recipe explicitly. This restates and makes operative
  the prior plan's decision 7 ("read-only by default"), which the pre-review v2 draft had
  silently dropped.
- `python-workflow`'s skill body states explicitly: never select `tidy` or `ship-it` unless the
  user named the recipe.

Cost: none of the four newly-gated skills lose anything — `python-refactor` was already
scheduled to flip `community` → `local` in this pass, and the other three are already local.

## Recipes — pipeline vs. ad-hoc

**In the pipeline** (`python-workflow <recipe>`):

```
critique:  scan → review → report
                     (report may recommend: "run python-architecture" — text, not an
                      auto-triggered arrow; nothing can invoke it but the user, by name)
           [read-only, 0 checkpoints]

tidy:      scan → 🛑 approve plan → patterns → quality-tools → verify → 🛑 approve terminal act
           [2 checkpoints: 1 and 3 — see below]

ship-it:   scan → 🛑 approve plan → document → patterns → quality-tools
                → 🛑 elect deep work → verify → 🛑 approve terminal act → git-commit
           [3 checkpoints]
```

**Ad-hoc — explicit call only, `disable-model-invocation: true`** (electable at `ship-it`'s
checkpoint 2 with the scan evidence attached, or invoked directly by name outside any recipe):
`python-testing-patterns`, `python-refactor`, `python-performance-optimization`,
`python-architecture`. `python-packaging` and `uv-package-manager` remain explicit-call by
convention but are not gated — see Enforcement above.

### Checkpoints — three, each answering a real question

The pre-review draft drew three checkpoints where two gated nothing (`ship-it`'s "approve
consequential work" sat between two already-safe stages with nothing left to elect; `tidy`'s
"diff review" was terminal, not a decision). Redefined so every stop has an answer:

1. **Approve the plan** — after evidence, before any write. *Decides:* which stages run,
   including which `python-scan` proposes to skip (see Evidence-conditioned execution, below).
2. **Elect deep work** *(`ship-it` only)* — after the safe tier, before `verify`. *Decides:*
   whether to hand off to `python-testing-patterns` / `python-refactor` /
   `python-performance-optimization`, with the scan evidence attached, as a real branch —
   this is what the chatgpt source doc originally asked for ("Which should I proceed with?").
   This is a deliberate, explicit softening of "never auto-triggered" to "never without an
   explicit election at this exact checkpoint" — the workflow can now hand off with consent,
   it still cannot decide to on its own.
3. **Approve the terminal act** — `git-commit` in `ship-it`; the already-applied, already
   behavior-preserving diff in `tidy` (which has no commit — this decides ship-as-is or
   revert, not "review a diff that already landed").

`tidy` has two stops (1 and 3); `ship-it` has three; `critique` has none, because nothing
mutates.

### Evidence-conditioned execution — proposed, not autonomous

The original version of this mechanism was under-specified: it measured docstring *presence*
not *adequacy* (a module of one-line stub docstrings would score 100% and skip the exact stage
`ship-it` was invoked for), ignored the tuned coverage bands adopted elsewhere in this document,
and had no evidence source at all for `python-quality-tools` (no `python-scan` analyzer touches
ruff or mypy findings). Fixed by making every skip a **proposal surfaced at checkpoint 1**, not
a silent runtime decision:

| Stage | Skip proposed when | Evidence source |
|---|---|---|
| `python-document` | docstring coverage ≥80% **and** type-hint coverage ≥90% | `check_documentation.py` |
| `python-patterns` | `find_dead_code`, `find_duplicates`, `find_unpythonic`, `find_overengineering` all empty | those four analyzers |
| `python-quality-tools` | never — no `python-scan` analyzer produces ruff/mypy evidence | — |

Checkpoint 1 then reads, e.g.: *"`python-document` — skip proposed (docstrings 94%, type hints
97%) · keep?"* — a line the user approves, not a behavior nothing tests.

`python-scan` is the only deterministic component this whole mechanism depends on, so it needs
a golden-test fixture: check a known-bad module into `tests/fixtures/` and assert `python-scan`'s
JSON output against it (the repo already has a `tests/` harness for exactly this kind of thing).
The prior plan's own build-order verification for `python-scan` was "output parses" — that
checks syntax, not content, and content is what the recipes now branch on.

## Cherry-pick findings (grounded in the actual source files where verified — see the standing caveat above for what isn't)

### `python-review` ← mattpocock/code-review + codementor/code-review-excellence + beagle/python-code-review + beagle/review-verification-protocol

| Source | Keep | Skip |
|---|---|---|
| mattpocock/code-review | Two-axis Standards/Spec report shape; parallel sub-agent dispatch so axes don't pollute each other; 12-smell Fowler baseline, each with a fix hint; "repo standard overrides baseline" rule | The diff-fixed-point mechanism as the *only* mode — must also run against a standalone finished module |
| codementor/code-review-excellence | Severity taxonomy (blocking/important/nit/suggestion/learning/praise) | All interpersonal/mentoring content — zero agentic value. **Retirement proposal dropped** (see below) — leave the source skill in place in `codementor` |
| beagle/python-code-review | Confirmed verbatim: the 5-step Gates workflow (Scope → false-positive screen → Evidence `[FILE:LINE]` mandatory → Verification protocol → Ship). "Valid Patterns — do NOT flag" list confirmed, 5 items. "Context-Sensitive Rules" confirmed but narrower than first implied — a 2-row table (generic exception handling, unused variables), not a broad framework | Its Python mechanical taxonomy — ruff/mypy-coverable, routed to `python-quality-tools` |
| **beagle/review-verification-protocol** *(new — the actual missed prize)* | This is what beagle's gate 4 actually references and nobody read the first pass. **Anti-confabulation gate 0**, run before any other check: echo the exact `file:line` and the code *read fresh this turn* — never from recollection or branch-name inference. Exists specifically because "an LLM under contextual priming will confidently flag code that is not in the file." This is the single most concrete, most valuable technique found across either upstream — it's the actual mechanism that makes an evidence gate work, not just the shape of one. Also: per-issue-type verification recipes (Unused Variable, Missing Validation, Type Assertion, Memory Leak/Race, Performance Issue) each with a checklist and named common false positives; Severity Calibration (Critical/Major/Minor/Informational, explicit inclusion criteria, a hard "Do NOT Flag At All" list, and a rule that Informational items never count toward an actionable-issue total); richer domain-split Valid-Patterns tables (Python-specific rows: `dict.get(key, [])`, `Optional[T]`, `cast()` after narrowing) | Non-Python-specific false-positive examples (React state setters, etc.) — filter to the Python-relevant subset |

**Spine, updated:** mattpocock's two-axis skeleton + smell baseline → codementor's severity
labels as presentation → beagle's Gates shape as the report structure → **`review-verification-protocol`'s anti-confabulation gate 0 as the actual enforcement**,
run first, before any finding is allowed to reach the Gates pipeline at all: no finding may be
reported without the reviewer having just re-read the exact lines it cites, in this pass, not
from memory. Everything after gate 0 (severity calibration, per-issue-type verification,
domain-split valid-patterns tables) is beagle's, harvested wholesale rather than reimplemented,
since the earlier "reimplement inline, don't take the dependency" call turns out to have been
about a skill we hadn't actually read.

**Overlap correction:** the earlier claim that beagle's checklist duplicated affaan-m's
Anti-Patterns table "near line-for-line" was overstated — only mutable default arguments
actually overlap between beagle's SKILL.md-level checklist and affaan-m's table. `type()` vs.
`isinstance`, `== None`, and `import *` are unique to affaan-m. Does not change the routing
decision (affaan-m's table still goes to `python-quality-tools`, not duplicated as prose here)
but the reasoning for it changes: not "avoid a near-duplicate," but "these are all
ruff-coverable and belong where fixes actually happen."

**Correction:** the earlier retirement proposal for `codementor/code-review-excellence` used
different reasoning than the paragraph keeping `git-commit` in the same plugin, despite both
skills being equally language-agnostic and equally covered by `codementor`'s stated purpose
("code review hygiene"). Dropped — harvest the taxonomy into `python-review`, leave the source
skill where it is, on the same reasoning already applied to `git-commit`. No irreversible action
needed for the cost of one plugin entry.

**Standards/Spec axis gap, fixed:** the two-axis design has no real Spec input for this
plugin's primary use case — a standalone finished script has no issue, PRD, or
`docs/agents/issue-tracker.md` to compare against, so the Spec axis would run empty on exactly
the case this plugin exists for (the prior plan raised this same objection when rejecting
code-review-as-steering and it re-surfaced here unanswered). Fixed by defining a second axis
that always has input: **Contract** — does the code do what its own docstrings, names, and type
hints claim? Two lenses now fire in the primary use case, and `python-review-lens` (below) has
two real dispatch targets instead of one that's usually empty.

### `python-patterns` ← affaan-m/python-patterns + python-simplifier prose

| Source | Keep | Skip |
|---|---|---|
| python-simplifier (prose) | The spine: Simplification Principles, before/after catalog (Extract-and-Name, Early Returns, Comprehensions, Dictionary Techniques, Context Managers), Over-Engineering anti-patterns, "when NOT to simplify" | — |
| affaan-m/python-patterns | Confirmed, every category present: EAFP vs. LBYL, type-hint depth (Protocol/TypeVar/modern syntax), dataclasses/NamedTuple, decorators, `__slots__`/generator memory idioms, the 10-row quick-reference table. **Newly added, not previously claimed**: Custom Exception Hierarchy pattern (`AppError` → `ValidationError`/`NotFoundError` base classes) and exception chaining (`raise ... from e`) — concrete and idiomatic, nothing else in this cherry-pick covers it | Anti-Patterns table (mutable defaults, `type()`/`isinstance`, `==None`, plus two the first pass missed — bare `except` and `import *`) — all five map to real ruff rules (B006, E721, E711, E722, F403) — route to `python-quality-tools`, don't duplicate as prose. Import Conventions section — that's isort/ruff `I001` territory, also `python-quality-tools`, not `python-packaging` as might be assumed. Concurrency section (threading/multiprocessing/async) — kept out of `python-patterns` on the same reasoning as before (high-stakes correctness, not an everyday-pass idiom), though flagged as the one judgment call here that's genuinely arguable rather than clean-cut |

**Second prose duplication the prior plan missed:** `python-simplifier`'s "Early Returns" /
"Dictionary Techniques" overlap `python-refactor`'s catalog entries "Guard Clauses" /
"Dictionary Dispatch." Fix: `python-patterns` owns the idiom-level version; `python-refactor`'s
catalog links out instead of re-describing, keeping its own catalog to genuinely structural
moves.

### `python-scan` ← python-simplifier/scripts/ + python-refactor/scripts/

Ships **~7 analyzers**, with two file-level corrections found by reading the actual scripts
(the pre-review table had these wrong):

| Script | Source | What it does | Verdict |
|---|---|---|---|
| `analyze_multi_metrics.py` | refactor | cognitive + cyclomatic + maintainability index | **Winner** for complexity |
| `analyze_complexity.py` | simplifier | bespoke AST cyclomatic-only | Retire — superseded |
| `measure_complexity.py` | refactor | bespoke cyclomatic+length AST walk | Retire — a second duplicate, within refactor's own set |
| `analyze_with_flake8.py` + `compare_flake8_reports.py` | refactor | shell out to flake8 + 8 plugins | Retire outright — refactor's own SKILL.md already declares ruff the primary stack |
| `check_documentation.py` | refactor | docstring + type-hint coverage | Keep — unique |
| `find_duplicates.py`, `find_dead_code.py`, `find_coupling_issues.py`, `find_overengineering.py`, `find_unpythonic.py` | simplifier | each unique, no counterpart | Keep all five |
| `find_code_smells.py` | simplifier | magic numbers, bare excepts, mutable defaults, type comparisons, god classes, long parameter lists | Mutable defaults/type comparisons are B006/E721 — already ruff-coverable, drop from here. God classes and long parameter lists are the part worth keeping |
| **`analyze_all.py`** | simplifier | **Corrected**: not a comparison harness — it's `python-simplifier`'s unified-JSON dispatcher, already wired to run 6 of the 7 keeper analyzers via subprocess and merge results | **Port to `python-scan` as its entry point.** Two edits: swap the `analyze_complexity.py` call for `analyze_multi_metrics.py`, add a `check_documentation.py` call. This is `python-scan`'s deliverable, already written — don't rebuild it from scratch |
| `compare_metrics.py` | refactor | before/after regression comparison | Stays in `python-refactor` — **but as written it imports `measure_complexity` and `check_documentation`, both of which move or retire under this plan and would break on import.** Fix: rewrite it to shell out to `python-scan` the way `analyze_all.py` shells out to its siblings, rather than importing modules directly |
| `benchmark_changes.py` | refactor | before/after benchmark comparison | Stays in `python-refactor`, no cross-import issue |

Refactor's metric-threshold table (cyclomatic <10/warn 15/err 20, cognitive <15/warn 20,
docstring >80%, type-hint >90%) is already tuned — used as `python-scan`'s pass/warn/fail bands.

### `python-testing-patterns` (already shipped) — gap check, not a redo

No real gap versus its sources. One cheap addition worth taking: mattpocock's sharper
one-line tautological-test definition ("expected value must come from a source independent of
the code's own computation").

## `python-architecture` — confirmed as skill #12, argument corrected

The original justification for this skill was wrong and has been replaced, not just patched.

**What was claimed:** the `improve-codebase-architecture` soft-dependency "degrades and skips"
when the target repo has no `CONTEXT.md`/ADR trail — checked against
`plugins/mattpocock/skills/improve-codebase-architecture/SKILL.md` directly: **false.** The
skill creates `CONTEXT.md` lazily if it's missing (§2, "Create the file lazily if it doesn't
exist") and treats ADRs as "if applicable." It does not skip.

**What actually holds, verified:** `improve-codebase-architecture` emits a self-contained HTML
file (Tailwind-via-CDN, Mermaid-via-CDN) opened in a browser. This plugin's own modularity rule
requires that where one skill's output feeds another, that output is structured — `FILE:LINE`
findings or JSON — never prose or a browser-rendered report requiring a second interpretation
pass. An HTML report cannot be consumed by `critique`'s report stage at all. *That* — not a
missing `CONTEXT.md` — is why the deep lane needs its own owned skill.

**Confirmed (user sign-off):** keep `python-architecture` as its own skill rather than folding
it into `python-review-lens` as a third lens. Reasoning: architecture audits (seams, deletion
test, whole-module structural analysis) are a materially different kind of work than a review
pass — different cost, different scope, and bundling them would make `python-review`'s cost
unpredictable. Discoverability is handled separately: `critique`'s report recommends running it
by name (see Recipes, above) rather than the recipe reaching for it automatically.

**Build:** harvest only `codebase-design`'s deletion test and module/interface/seam vocabulary
from the `mattpocock` plugin, dropping the `CONTEXT.md`/ADR requirement and the `grilling`
dependency entirely. `disable-model-invocation: true` (see Enforcement).

`git-commit` remains the one soft cross-plugin dependency left in this plugin, kept deliberately
differently from the old `improve-codebase-architecture` reference: it's a single skill with no
precondition chain (unlike the three-plugin architecture chain that motivated owning
`python-architecture`), and it's genuinely reusable if a second language pack is ever added.
It lives in `codementor`, whose own stated purpose is "git workflow and code review hygiene
skills" — already the right home. No change proposed.

## Subagent dispatch — in-skill instructions, not static profile files

The original proposal (standalone `python-review-lens.md` / `python-performance-profiler.md`
agent files) was reconsidered after checking how Anthropic's own reference plugin,
`anthropics/claude-code`'s `code-review` plugin, implements the identical need — parallel
independent review lenses with false-positive filtering. **It ships zero `agents/*.md` files.**
The whole pattern lives as plain dispatch instructions inside one prompt (their case: a
slash-command; ours: a skill), which spawns Agent-tool subagents on demand, each with an inline
persona and constraints written into the prompt at dispatch time — exactly how this repo's own
`adversarial-review` skill already works.

**This resolves the build-mechanism question entirely — no `build.py` `agents:` block needed.**
Confirmed separately: Claude Code *does* read a plugin-root `agents/` directory (official docs,
lowest-priority scope, drops hooks/mcpServers/permissionMode — irrelevant here since neither
use case needs them) — but that mechanism isn't even required for this design, since nothing
is being pre-authored as a static file.

**`python-review`'s own `SKILL.md` carries the dispatch instructions** for its two lenses
(Standards, Contract): spawn two parallel Agent-tool subagents, one per axis, using
Anthropic's proven refinements rather than beagle's vaguer "gate" framing —
- **Numeric confidence scoring (0-100, threshold 80)** as the false-positive filter, concrete
  and provenly-working, in place of a suppression-list-only approach.
- **A second validation pass**: every flagged issue is re-checked by a fresh subagent before it
  ships, layered on top of `review-verification-protocol`'s anti-confabulation gate 0 (re-read
  the cited lines fresh, this pass) — two independent defenses against hallucinated findings,
  not one.
- **Model tier matched to task weight**: sonnet for the Standards/Contract compliance lenses,
  opus for anything judgment-heavy enough to warrant it, matching Anthropic's own
  haiku/sonnet/opus split by task.

**`python-performance-optimization`'s `SKILL.md` carries a similar one-liner**: run the
profiling job in an isolated Agent-tool subagent so a long, verbose profiling pass doesn't fill
the main session's context. Same non-mechanism: no static file, no build change.

No profile-equivalent instructions for `python-architecture`/`python-refactor`/
`python-testing-patterns` — single-session, explicit-call, no fan-out need.

## Open items — all resolved

1. **`python-architecture` as owned skill** — resolved, kept as its own skill (see above).
2. **CLI-invocation-design gap in `python-packaging`** — resolved, folded in. The skill gains a
   CLI-surface-design section (argument ergonomics, not just entry-point wiring) alongside its
   existing packaging content. Since this is now a hand-maintained addition rather than
   verbatim community content, `python-packaging` flips `source: community` → `local` in
   `bundles.yaml`, the same pattern already used for `python-testing-patterns` and
   `python-performance-optimization`.
3. **Workflow-discipline gap in `python-performance-optimization`** — resolved, folded in.
   Confirmed real by independent file inspection (no `## Workflow` section, unlike
   `python-testing-patterns`'s explicit numbered one). Adds the enforced baseline →
   prove-there's-a-problem → profile → propose → 🛑 approve → optimize → re-benchmark → compare
   sequence the chatgpt source doc asked for, plus a ported benchmark-comparison script (from
   `python-refactor`'s `compare_metrics.py` / `benchmark_changes.py` pattern, once that script's
   own import fix from the `python-scan` table above lands) instead of reinventing one.

This plan is now finalized. The `affaan-m`/`beagle` provenance caveat is resolved (see the top
of this document) — both were independently read and cross-checked twice, with citations; the
one residual gap (beagle's untouched reference files, affaan-m's mirror directories) is
low-value and non-blocking, not a reason to hold the plan open further.

## Build order

Corrected from the prior plan given the fixes above. New: a walking skeleton inserted early
(step 2a), so the orchestrator — the part of this design that is actually novel — gets
exercised while it's still cheap to change, instead of being the last thing built in a solo,
intermittent project where the realistic outcome of a ten-step queue is four steps done and six
never reached.

| # | Step | Verify |
|---|---|---|
| 1 | ~~Fetch and read `affaan-m/everything-claude-code` and `existential-birds/beagle`~~ — **done**, twice, with citations (see cherry-pick tables above, including `beagle/review-verification-protocol`, found on the second pass). Neither added as a `community` entry, per the harvest-don't-vendor rule. | Satisfied |
| 2 | `python-scan` — port `analyze_all.py` as entry point, consolidate the 7 keeper analyzers, fix `find_code_smells.py` scope, use refactor's tuned thresholds | Runs on this repo and a scratch project; output matches a golden-test fixture, not just "parses" |
| **2a** | **`python-workflow` — `critique` only.** `scan → report`, no `review` yet, no checkpoints (read-only). | `python-workflow critique` runs end-to-end on a scratch project, writes zero files |
| 3 | `python-quality-tools` — the fix loop | Runs against a deliberately dirty scratch project; loop converges |
| 4 | `python-patterns` — merge | Diff on a scratch project is behavior-preserving; tests still green. `tidy` recipe now reachable end-to-end |
| 5 | `python-document` | Produces docstrings/annotations without changing behavior. `ship-it`'s safe tier now reachable |
| 6 | `python-review` — merge, with the Contract axis | Findings match `python-scan`'s flags plus judgment beyond it; both axes produce output on a spec-less module |
| 7 | `python-architecture` — harvest `codebase-design` only | Runs standalone on a module with no `CONTEXT.md`; emits structured findings, not an HTML report |
| 8 | `python-refactor` rework — port fixed `compare_metrics.py`, keep `benchmark_changes.py`, strip duplicated analyzers, fix stale refs, flip to `local`, add `disable-model-invocation` | `./build.py --plugin pythonista`; `compare_metrics.py` imports cleanly; git diff shows only intended changes |
| 9 | Retire `python-simplifier` | Removed from `bundles.yaml`; nothing references it |
| 10 | `python-workflow` — complete: add `tidy`, `ship-it`, the three real checkpoints, evidence-conditioned skip proposals, soft-dep probing for `git-commit`, `disable-model-invocation` default-to-`critique` behavior | Each recipe runs end to end on a scratch project |
| 11 | `python-performance-optimization` — add the enforced Workflow section (baseline → prove problem → profile → propose → 🛑 approve → optimize → re-benchmark → compare) and port a benchmark-comparison script | Run on a scratch script with a real bottleneck; the skill refuses to "optimize" without first showing baseline evidence, and the approval gate is honored |
| 12 | `python-packaging` — add CLI surface-design section, flip `source: community` → `local` | Skill proposes a CLI argument structure (not just entry-point wiring) for a scratch script being turned into a tool |

Use `skillcraft:skill-creator` for every new/merged/revised skill (steps 2, 2a, 3, 4, 5, 6, 7, 10, 11, 12).

### Repo mechanics — non-negotiable

- New/merged skills are authored in `skills/<name>/` (source of truth) and declared
  `source: local` in `bundles.yaml`.
- Regenerate with `./build.py --plugin pythonista` — never a bare `./build.py`.
- Never hand-edit anything under `plugins/`.
- Record the merge rationale in each merged skill's header so "why two became one" survives.
