# Pythonista plugin plan

Synthesis of `pythonista-plugin-design-chatgpt.md` and `pythonista-plugin-design-claude.md`,
reconciled against what this repo actually contains. Those two docs are the raw input; this
one is the agreed shape. If a downstream change contradicts something here, change this file
first.

## Framing

The task is **not** "build a pipeline." It is, in order:

1. **Identify** the capabilities actually needed.
2. **Modularize** them so each has one job and no overlap.
3. **Place** them — what is a script, what is a skill, what is a recipe.
4. **Recompose** a few of them into named workflows.

There is no single true pipeline. There are atomic capabilities and several legitimate
compositions of them.

## Settled decisions

| # | Decision | Resolution |
|---|---|---|
| 1 | Language scope | **Self-contained Python.** No generic core layer. Correct in theory, not worth building for a single-language user. Two existing agnostic skills are *referenced*, not duplicated (see [Soft dependencies](#soft-dependencies)). |
| 2 | Steering step | **Not code-review.** Steering = deterministic evidence + user intent. See [Why not code-review](#why-code-review-is-not-the-steering-step). |
| 3 | Merge semantics | **Synthesize, don't adopt.** Every merge produces our own local skill that inherits the best of its sources. Sources are read and harvested, never vendored as-is. |
| 4 | Documentation skill | **Yes.** "Finished script → module summary, docstrings, annotations, comments" is a named use case. Own skill, explicit call, optional lane member. |
| 5 | `improve-codebase-architecture` | **In scope**, as a deep-work branch in the `critique` recipe — not as a pipeline stage. |
| 6 | Orchestrator mechanism | **A skill, not a command.** `build.py` has no `commands:` or `agents:` block; Claude Code already exposes skills as `/pythonista:<name>`. Zero build changes. |
| 7 | Default posture | **Read-only by default.** Every recipe that mutates is opt-in by name. |

---

## Why code-review is not the steering step

Three concrete reasons, all discovered in the vendored skills:

1. **`mattpocock/code-review` is diff-scoped.** It reviews `git diff <fixed-point>...HEAD`
   along Standards and Spec axes, and refuses to run without a resolvable ref and a
   non-empty diff. It also expects `docs/agents/issue-tracker.md`. For "here is a finished
   script, make it good," there is no fixed point and no spec. Wrong lens.
2. **Review output is prose; routing needs structure.** A steering step has to produce
   something the next stage can branch on. A narrative report can't be branched on without
   a second interpretation pass.
3. **Review is expensive and intent-blind.** It reads everything and then guesses what you
   wanted. When you already know you want docstrings, a full review is pure overhead.

**Replacement: evidence + intent.**

- **Evidence** comes from `python-scan` — deterministic analyzers, seconds to run, structured
  JSON out. Complexity, dead code, duplication, coupling, YAGNI, docstring coverage,
  unpythonic constructs.
- **Intent** comes from the user, stated or inferred from which recipe they invoked.

`python-review` becomes one *lane member*, invoked when the intent is genuinely "critique
this" or when a diff/PR is the subject. It stops being a mandatory toll booth.

---

## Layer model

```
Layer 2   Recipes         critique · tidy · ship-it        (compositions)
Layer 1   Capabilities    one job each, independently invocable
Layer 0   Analysis        shared deterministic scripts, no judgment
```

Layer 0 lives in `skills/python-scan/scripts/` and is called by path from Layer 1 skills.
This is only possible because the plugin is self-contained (decision 1).

---

## Target inventory

Prefix stays `python-*`, matching what's there.

### Layer 0 + evidence

| Skill | Status | Job | Built from |
|---|---|---|---|
| `python-scan` | **NEW (merge)** | Read-only deterministic analysis. Emits structured findings. The steering input. | `python-simplifier/scripts/` (8 analyzers) + `python-refactor/scripts/` (7 analyzers), deduped |

### Judgment, read-only

| Skill | Status | Job | Built from |
|---|---|---|---|
| `python-review` | **NEW (merge)** | Judgment-based critique of a module *or* a diff. Prioritized findings with severity. | `mattpocock/code-review` (smell baseline, two-axis split, parallel sub-agents) + `codementor/code-review-excellence` (severity taxonomy, review-scope checklist) + `existential-birds/beagle/python-code-review` |

### Mutation — safe tier

| Skill | Status | Job | Built from |
|---|---|---|---|
| `python-patterns` | **NEW (merge)** | Idioms, dead code, duplication, YAGNI. Behavior-preserving. Absorbs "simplify" wholesale. | `affaan-m/everything-claude-code/python-patterns` + `python-simplifier` prose/idioms + beagle |
| `python-document` | **NEW** | Module summaries, docstrings, type annotations, comments. Consistency with project conventions. | Authored |
| `python-quality-tools` | **NEW** | Deterministic detect → fix → rerun loop: ruff format, ruff check --fix, type check, docstring coverage, secret scan, dependency audit. Bootstraps missing tooling. | Authored |

### Mutation — structural tier, explicit call only

| Skill | Status | Job |
|---|---|---|
| `python-refactor` | **REWORK** | Module-level restructuring. Strip its duplicated analyzers (moved to `python-scan`), fix stale cross-refs, keep `REGRESSION_PREVENTION.md` and the metric targets. Flip `source: community` → `local`. |
| `python-testing-patterns` | ✅ **done** | Already local and synthesized from `mattpocock/tdd` + `superpowers/test-driven-development`. |
| `python-performance-optimization` | ✅ **done** | Already local, with `live_dashboard.py` + `profile_report.py`. Evidence-first. |

### Unchanged

| Skill | Status |
|---|---|
| `python-packaging` | keep, community |
| `uv-package-manager` | keep, community |

### Orchestration

| Skill | Status | Job |
|---|---|---|
| `python-workflow` | **NEW** | Holds the recipes, the checkpoints, and the routing. Contains no expertise of its own. |

### Retired

| Skill | Why |
|---|---|
| `python-simplifier` | Split: scripts → `python-scan`, prose/idioms → `python-patterns`. Nothing is lost. |

**Net: 6 → 11 skills.** Two already exist. Six need authoring, one needs rework, one retires.

> **Trim option if 11 is too many:** fold `python-scan` into `python-quality-tools` as a
> `--report` mode → 10. Rejected for now because the two have genuinely different outputs
> (evidence for a human/judgment skill vs. auto-applied fixes), but it is the first thing
> to cut if the set feels bloated.

---

## Soft dependencies

Self-contained means self-contained *for Python*. Two skills are agnostic, already good,
and get referenced rather than cloned:

| Skill | Lives in | Used by | If absent |
|---|---|---|---|
| `git-commit` | `codementor` | `ship-it` recipe | Recipe stops at "changes ready to commit" and says why |
| `improve-codebase-architecture` | `mattpocock` | `critique` recipe, deep lane | Lane is skipped with a note |

`improve-codebase-architecture` additionally needs `codebase-design` and `domain-modeling`
(`mattpocock`) **and `grilling` (`essentials`)** — a three-plugin chain — plus `CONTEXT.md` /
`docs/adr/` in the target repo. `python-workflow` must probe for it and degrade, never fail.

> **Open alternative:** write a leaner Python-flavoured `python-architecture` that harvests
> the deepening / deletion-test vocabulary without the CONTEXT.md, ADR, and grilling
> machinery. Cheaper to run, no cross-plugin chain, but duplicates good work. Deferred —
> revisit if the soft dependency proves annoying in practice.

---

## Recipes

Three named compositions. Each is one entry in `python-workflow`.

### `critique` — read-only, no writes at all

```
python-scan  ──▶  python-review  ──▶  prioritized report
                        │
                        └─(optional deep lane)─▶ improve-codebase-architecture
```

Answers "what is wrong and what matters." Produces recommendations only. Zero checkpoints —
nothing to approve, because nothing changes.

### `tidy` — safe tier, behavior-preserving

```
python-scan ──▶ 🛑 approve plan ──▶ python-patterns ──▶ python-quality-tools
                                                              │
                                                              ▼
                                                    verify (existing tests)
                                                              │
                                                              ▼
                                                    🛑 diff review
```

No commit. No tests written. No structural change. If no test suite exists, verify degrades
to a warning, not a hard gate.

### `ship-it` — finished script → committed

```
python-scan ──▶ 🛑 approve plan ──▶ python-document ──▶ python-patterns
                                                              │
                                                              ▼
                                                    python-quality-tools
                                                              │
                                                              ▼
                                            🛑 consequential-work checkpoint
                                       (testing / refactor / performance — user picks)
                                                              │
                                                              ▼
                                                    final verification
                                                              │
                                                              ▼
                                                    🛑 approve commit
```

### Deep work — invoked directly, never auto-triggered

`python-testing-patterns` · `python-refactor` · `python-performance-optimization` ·
`improve-codebase-architecture`

A recipe may **recommend** these at a checkpoint. Only the user starts them.

### Checkpoint rule

**Three checkpoints, at these boundaries only:**

1. **Approve the plan** — after evidence, before any write.
2. **Approve consequential work** — before anything structural, behavior-changing, or expensive.
3. **Approve the commit** — the only irreversible act.

Five (every read→write transition) is checkpoint fatigue. Two lets judgment-based edits
land unreviewed. Three is the compromise, and it is a decision, not a law — revise if it
chafes.

---

## Known problems to fix while we are in here

- **Duplicate analyzers.** `python-simplifier/scripts/analyze_complexity.py` and
  `python-refactor/scripts/analyze_multi_metrics.py` overlap. `python-scan` must pick one
  implementation per concern, not ship both.
- **Stale cross-references.** pythonista skills name `clean-code`, `python-tdd`,
  `async-python-patterns`, and `django-simplifier` — none exist in this marketplace. Fix
  during the `python-refactor` rework.
- **`code-review-excellence` after harvesting.** It is a human-team-practice document
  (feedback etiquette, mentoring, morale) with little agentic value. Once its severity
  taxonomy and scope checklist are in `python-review`, propose retiring it from
  `codementor`. `mattpocock/code-review` **stays** — it is diff/PR-scoped and agnostic, a
  genuinely different tool.

---

## Build order

Each step ends with a runnable check. Do not proceed on inspection alone.

| # | Step | Verify |
|---|---|---|
| 1 | Fetch and read the two new upstreams for harvesting: `affaan-m/everything-claude-code` (`python-patterns`), `existential-birds/beagle` (`python-code-review`). Read only — do **not** add as `community` entries. | Source notes captured before any authoring |
| 2 | `python-scan` — consolidate both script sets, one implementation per concern, structured output | Run it on this repo and on a scratch Python project; output parses |
| 3 | `python-quality-tools` — the fix loop | Run against a deliberately dirty scratch project; loop converges, reports what it left |
| 4 | `python-patterns` — merge | Diff on a scratch project is behavior-preserving; tests still green |
| 5 | `python-document` | Produces docstrings/annotations on an undocumented scratch script without changing behavior |
| 6 | `python-review` — merge | Findings on a known-bad scratch file match what `python-scan` flagged, plus judgment beyond it |
| 7 | `python-refactor` rework — strip dup scripts, fix stale refs, flip to `local` | `./build.py --plugin pythonista`, git diff shows only intended changes |
| 8 | Retire `python-simplifier` | Removed from `bundles.yaml`; nothing references it |
| 9 | `python-workflow` — recipes, checkpoints, soft-dependency probing | Each recipe runs end to end on a scratch project; `critique` writes nothing |

Use `skillcraft:skill-creator` for every new skill (steps 2–6, 9).

### Repo mechanics — non-negotiable

- New/merged skills are authored in `skills/<name>/` (source of truth) and declared
  `source: local` in `bundles.yaml`.
- Regenerate with `./build.py --plugin pythonista` — **never** a bare `./build.py` (it
  re-fetches every community skill and pulls unrelated upstream drift into the diff).
- Never hand-edit anything under `plugins/`.
- Record the merge rationale in each merged skill's header so "why two became one" survives.

---

## Open questions

1. **Is 11 the right size?** The trim option above takes it to 10. Say so before step 2 if
   `python-scan` should be a mode of `python-quality-tools` instead of its own skill.
2. **Soft dependency vs. own architecture skill** — deferred, see [Soft dependencies](#soft-dependencies).
3. **Recipe naming** — `critique` / `tidy` / `ship-it` are placeholders. They become
   `/pythonista:python-workflow` arguments or three separate skills; decide at step 9.
