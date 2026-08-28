# Adversarial Review — Pythonista plugin plan v2 draft

**Reviewer:** Staff engineer who has built and killed three internal agentic-workflow systems; reads orchestration designs for the seam where checkpoints become rubber stamps and skill boundaries stop matching how people actually ask.
**Artifact:** `docs/pythonista-plugin-plan-v2-draft.md`
**Threat model:** Time and disuse. Six months of solo, intermittent use. The adversary wants the checkpoints skimmed, the deep-work skills never invoked, and the evidence-conditioned logic quietly wrong with nothing to notice.
**Assumptions made:**
- Usage-pattern risk counts as much as architectural cleanliness (confirmed by the brief).
- The build order is executed intermittently over months, not in one sustained push. If it is one push, F6 drops to Low.
- `bundles.yaml` step-1 fetching has not happened yet — `affaan-m` and `existential-birds/beagle` appear nowhere in `bundles.yaml` or the tree.

**Correction to the brief:** I was told to treat upstream-skill claims as unverifiable. Most were not. `mattpocock/code-review`, `mattpocock/improve-codebase-architecture`, `codementor/*`, `build.py`, and every `python-simplifier` / `python-refactor` script are vendored in this worktree and I read them. Findings F4, F5, F7 and F8 are grounded in those files, with line references. Only the `beagle` and `affaan-m` claims remain untested — see §6.

## 1. Verdict

The layer model, the recipe shape, and the merge decisions hold up; I tried to break the two rejections you flagged for scrutiny and both survive. What does not hold is enforcement: every rule that keeps this system safe — "never auto-triggered," "read-only by default," "approve consequential work" — is prose in a design document with no mechanism behind it, and two of the four drawn checkpoints gate nothing at all. Separately, the cherry-pick tables are strong except in two places where I checked the actual files and the plan breaks code: `compare_metrics.py` imports two modules the plan retires and relocates, and `analyze_all.py` is assigned to stay in a skill it was never in and which the plan retires. Fixing the checkpoint semantics is a rewrite of one section and it unblocks most of the rest.

**Standing:** Sound with gaps

## 2. What must survive

- **The mutate / no-mutate line as the organizing principle.** It is doing more work than the layer diagram is, and it is what makes `python-scan` vs `python-quality-tools` a real boundary rather than a taxonomic one. Do not blur it.
- **`python-scan` as a separate skill.** The rejection of the 10-skill trim holds. The `--fix`-counterpart argument has a small wobble (see §5) but the underlying ownership line is right.
- **One `python-workflow` with recipe args.** Right answer. The argument for it is the weaker of the two available (F11), but the conclusion is not in doubt.
- **Harvest-don't-vendor.** The cherry-pick tables with explicit Keep/Skip columns are the most useful thing in the document — they are the only place the *reasoning* for a merge is recoverable six months later.
- **Reusing `python-refactor`'s tuned threshold table** (cyclomatic <10/15/20, docstring >80%, type-hint >90%) instead of inventing bands. Keep, and lean on it harder — see F3.

## 3. Findings

### F1 · High · DEFECT — Every safety rule in this design is prose, and the one mechanism that enforces it is already in the marketplace and unused

- **Where:** "Ad-hoc — explicit call only, never auto-triggered"; the skill inventory rows for `python-refactor`, `python-packaging`, `uv-package-manager`; and the silent loss of the prior plan's settled decision 7, "Read-only by default. Every recipe that mutates is opt-in by name," which appears nowhere in v2.
- **What:** Six skills are declared explicit-call-only. Nothing makes them so. `plugins/pythonista/skills/python-refactor/SKILL.md:5` currently reads `TRIGGER WHEN: the user asks for "readable", "maintainable" or "clean" code` — the plan changes nothing about that. `python-packaging` and `uv-package-manager` are marked "unchanged from community," so their auto-triggering descriptions ship as-is. Meanwhile this marketplace already has the enforcement primitive: `disable-model-invocation: true` appears in 14 SKILL.md files (`mattpocock/improve-codebase-architecture:4`, `codementor/git-cleanup:4`, `essentials/grill-me:4`, …) and in zero pythonista skills. The draft never mentions it.
- **Why it matters:** This is the exact rot the review is standing in for. In six months you type "clean this up" and `python-refactor` fires — the skill the plan classifies as structural-tier, explicit-call-only, deep work. The rule was never wrong; it just had nothing holding it. And dropping decision 7 compounds it: one skill, `python-workflow`, whose description must cover both a read-only critique and a recipe that ends in `git-commit`.
- **The probe:** Grep the plan for the mechanism that prevents `python-refactor` from auto-invoking. There isn't one. Then read `python-simplifier`'s shipped description — "Triggers on … 'refactor this', 'clean this up', 'analyze this codebase'" — and note that this is the collision the plan is supposed to end.
- **Remedy:** Three mechanical changes, one line each:
  1. Add `disable-model-invocation: true` to the four ad-hoc skills that mutate or are expensive: `python-refactor`, `python-testing-patterns`, `python-performance-optimization`, `python-architecture`. Leave `python-packaging` and `uv-package-manager` auto-invocable — they are read-mostly references and the harm is low.
  2. Restate decision 7 in v2 and make it operative: **`python-workflow` with no recipe argument runs `critique`.** `tidy` and `ship-it` require the user to name the recipe.
  3. `python-workflow`'s frontmatter `description` advertises only the read-only entry point. Add to the skill body: "Never select `tidy` or `ship-it` unless the user named the recipe."
- **Trades:** Flipping `python-refactor` to `local` was already planned; `python-testing-patterns` and `python-performance-optimization` are already local, so this costs nothing there. You give up ambient discoverability of the deep-work skills — you will have to remember they exist, which is the same problem F6 is about.
- **Confidence:** High. Verified against the shipped frontmatter and a marketplace-wide grep.

### F2 · High · DEFECT — Two of the four drawn checkpoints gate nothing

- **Where:** the `ship-it` diagram (`🛑 approve consequential work`) and the `tidy` diagram (`🛑 diff review`), against the "Checkpoints: three" rule.
- **What:** In `ship-it` as drawn, checkpoint 2 sits between `quality-tools` and `verify`. Everything before it — `document`, `patterns`, `quality-tools` — is declared safe tier. Everything after it is `verify` (running the existing suite) and then checkpoint 3. And the ad-hoc rule forbids the recipe from starting the deep-work skills that would *be* the consequential work: "a checkpoint may *recommend*, only the user *starts*." So checkpoint 2 gates a test run. In `tidy`, the `diff review` stop is terminal — nothing follows it, so it is a report, not a gate, and it is not one of the three named boundaries (plan / consequential work / commit) either.
- **Why it matters:** A stop that blocks nothing is trained away. You press enter on it forty times, and the forty-first time it is checkpoint 3 sitting in the same visual position and you press enter on that too. This is how the checkpoint design fails — not by having the wrong number, but by having stops the user cannot answer, next to stops they must.
- **The probe:** Name one thing checkpoint 2 in `ship-it` prevents. Then name what the user is deciding at `tidy`'s diff review, given that the changes are already applied, are declared behavior-preserving, and nothing irreversible follows.
- **Remedy:** Keep three; make each one answer a question. Rewrite the checkpoint block as:
  1. **Approve the plan** — after evidence, before any write. *Decides:* which stages run, including which `python-scan` says to skip (see F3).
  2. **Elect deep work** — after the safe tier, before `verify`. *Decides:* whether to hand off to `python-testing-patterns` / `python-refactor` / `python-performance-optimization`, with the scan evidence attached. This makes it a real branch, which is what the chatgpt source doc asked for ("Which should I proceed with?"), instead of a notice.
  3. **Approve the terminal act** — `git-commit` in `ship-it`; the accepted diff in `tidy`, which has no commit. *Decides:* ship or revert.
  Then `tidy` has two stops (1 and 3), `ship-it` has three, `critique` has none, and every stop has an answer.
- **Trades:** Checkpoint 2 becoming a real branch means `ship-it` can now launch a deep-work skill, which softens "never auto-triggered" to "never without an explicit election." That is a position given up; it is also the only way the stop earns its place.
- **Confidence:** High.

### F3 · High · DEFECT — Evidence-conditioned execution is one example long, the example is wrong, and two of three stages have no evidence to condition on

- **Where:** "New in this draft … evidence-conditioned execution."
- **What:** The mechanism is specified entirely by one example — don't run `python-document` if docstring coverage is 100%. Three problems. (a) `check_documentation.py` measures docstring *presence*, not adequacy; a module of one-line stubs scores 100% and skips the exact stage the user invoked `ship-it` for. (b) The draft already adopts refactor's tuned bands (docstring >80%, type-hint >90%) two sections earlier and then ignores them for a hand-picked 100%. (c) `python-quality-tools` has no evidence source at all: `python-scan`'s seven analyzers produce complexity, dedup, dead code, coupling, docs and idiom signals, and the flake8 scripts are retired, so nothing in scan output speaks to ruff or mypy. The stage can never be skipped. That leaves the mechanism applying to at most one of `tidy`'s two mutating stages. There is also no override — the draft never says what a user does when a skip is wrong.
- **Why it matters:** This is the newest logic in the design, it runs at runtime, it is invisible when it fires, and nothing verifies it. It is the single most likely thing here to be silently wrong in six months, because a wrong skip looks identical to a correct one: a line saying "skipped — nothing to do."
- **The probe:** Run `ship-it` on a module whose every function has a one-line `"""Does the thing."""`. Docstring coverage is 100%. `python-document` skips. Now name the stage that would have caught it. Second probe: state the scan finding that causes `python-quality-tools` to skip.
- **Remedy:** Two parts, both cheap.
  1. Replace the paragraph with an explicit table, and move the decision to checkpoint 1 so it is proposed, not taken:

     | Stage | Skip proposed when | Evidence source |
     |---|---|---|
     | `python-document` | docstring coverage ≥80% **and** type-hint coverage ≥90% | `check_documentation.py` |
     | `python-patterns` | `find_dead_code`, `find_duplicates`, `find_unpythonic`, `find_overengineering` all empty | those four |
     | `python-quality-tools` | never — no analyzer produces ruff/mypy evidence | — |

     The checkpoint-1 plan then reads: `python-document — skip proposed (docstrings 94%, type hints 97%) · keep?` The skip becomes a line a human approves rather than a runtime behavior nothing tests.
  2. Make the evidence layer verifiable. `python-scan` is the only deterministic component in the whole design and every conditional decision reads from it. Check a known-bad fixture module into `tests/fixtures/` and golden-test `python-scan`'s JSON against it — the repo already has a `tests/` harness. The prior plan's step-2 verify is "output parses"; that checks syntax, not content, and content is what the recipes branch on.
- **Trades:** Part 1 gives up the autonomy that made the mechanism appealing — the pipeline no longer optimizes itself silently. That is the point. Part 2 adds a fixture and a test file to a repo that has neither for skills.
- **Confidence:** High on (a) and (c), which are readable off the script inventory. Medium on whether you want the skip visible at all; if you would rather keep it autonomous, at minimum fix the threshold and add the override.

### F4 · High · DEFECT — The sign-off argument for skill #12 rests on a claim its own source file contradicts

- **Where:** "`python-architecture` — the one inventory change," and open item 1.
- **What:** The load-bearing sentence is: "the soft-dependency would degrade-and-skip most of the times it's actually invoked." I read `plugins/mattpocock/skills/improve-codebase-architecture/SKILL.md`. It does not skip when `CONTEXT.md` is absent. Line 68: *"Add the term to `CONTEXT.md`. Create the file lazily if it doesn't exist."* ADRs are handled as "if applicable" (line 56). The dependency table's own entry — "domain-modeling … near-zero value without an existing CONTEXT.md" — is true and irrelevant, because the skill does not require one. The conclusion may still be right; the reason given for it is not.
- **Why it matters:** You are about to sign off on adding a twelfth skill on the basis of a mechanism claim that is false. If you sign off and later re-derive the argument, it collapses and the skill looks unmotivated — which is how a skill ends up in an inventory that nobody invokes.
- **The probe:** Open the source and search for the skip. There isn't one. Then ask the sharper question the draft never asks: what does `improve-codebase-architecture` actually *emit*? A self-contained HTML file written to `$TMPDIR`, styled with Tailwind-via-CDN and Mermaid-via-CDN, opened in a browser (SKILL.md §2). It is also `disable-model-invocation: true`.
- **Remedy:** Keep the conclusion, replace the argument with the one that holds — and it is a stronger one, drawn from this document's own rules:
  > `improve-codebase-architecture` emits a browser-opened HTML report. This plugin's modularity test requires that where one skill's output feeds another, that output is structured — `FILE:LINE` findings or JSON, never prose requiring a second interpretation pass. An HTML report opened in a browser cannot be consumed by `critique`'s report stage at all. That, not a missing `CONTEXT.md`, is why the deep lane needs an owned skill.

  Then consider the cheaper shape before committing to a twelfth skill: **make it `python-review`'s third lens.** The draft already proposes a `python-review-lens` subagent that runs one axis of a multi-axis analysis; an `architecture` lens carrying `codebase-design`'s deletion test and module/interface/seam vocabulary reuses that machinery exactly, keeps the count at 11, still removes the cross-plugin chain, and — critically — is reachable without the user having to already know their problem is architectural rather than review-level, which is the thing they invoked the tool to find out. It also gives `python-review-lens` a second lens that actually fires, which F5 says it currently lacks.
- **Trades:** The lens option gives up a nameable `/pythonista:python-architecture` entry point, and merges two things the layer model would rather keep apart. If you want the standalone skill anyway, take the replacement argument and ship it — but ship it with the real reason.
- **Confidence:** High on the false premise (read the file). Medium on the lens recommendation — it depends on how often you would invoke architecture review on its own.

### F5 · High · DEFECT — `compare_metrics.py` will not import after this plan, and `analyze_all.py` is assigned to a skill it was never in

- **Where:** the `python-scan` cherry-pick table, last two rows.
- **What:** Two concrete errors in the document's centerpiece table, both verified by reading the files.
  1. **Broken imports.** `plugins/pythonista/skills/python-refactor/scripts/compare_metrics.py:17-18` does `import measure_complexity` and `import check_documentation`. The table retires `measure_complexity.py` ("a second duplicate") and moves `check_documentation.py` to `python-scan` ("Keep — unique"), while leaving `compare_metrics.py` in `python-refactor` ("stays there"). After the plan, it imports one module that no longer exists and one that lives in a different skill directory. Open item 3 then proposes porting `compare_metrics.py` into `python-performance-optimization`, which would carry the same two broken imports into a second skill.
  2. **Orphaned orchestrator.** The row lists `analyze_all.py` under Source "both." It is `python-simplifier`'s only — and `python-simplifier` is retired. It cannot "stay there." Worse, the verdict misreads what it is: it is not a before/after comparison harness, it is the unified-JSON dispatcher that runs the sibling analyzers via subprocess with `--format json` and merges the results (`analyze_all.py:14-57`). It already dispatches six of `python-scan`'s seven keeps: `find_code_smells`, `find_overengineering`, `find_dead_code`, `find_unpythonic`, `find_coupling_issues`, `find_duplicates`. That is `python-scan`'s deliverable, already written, and the plan throws it away.
- **Why it matters:** Both land at build steps 2 and 7 — the first real work after this document. You rewrite an orchestrator you already own, and you ship a `python-refactor` whose regression-prevention scripts crash on import. The second is silent until someone runs it.
- **The probe:** `head -20 plugins/pythonista/skills/python-refactor/scripts/compare_metrics.py`. Then `grep run_analyzer plugins/pythonista/skills/python-simplifier/scripts/analyze_all.py`.
- **Remedy:** Split the last row into three, and fix the verdicts:

  | Script | Source | Verdict |
  |---|---|---|
  | `analyze_all.py` | simplifier | **Port to `python-scan` as its entry point.** Two edits: swap the `analyze_complexity.py` call for `analyze_multi_metrics.py`, add a `check_documentation.py` call. |
  | `compare_metrics.py` | refactor | Stays in `python-refactor` — **but it imports `measure_complexity` and `check_documentation`.** Either keep `measure_complexity.py` (contradicting its retirement) or rewrite `compare_metrics.py` to shell out to `python-scan` the way `analyze_all.py` already shells out to its siblings. |
  | `benchmark_changes.py` | refactor | Stays. No cross-imports. |

  The second row also settles open item 3's "port `compare_metrics.py` to performance-optimization" question: not until its imports are resolved.
- **Trades:** Keeping `measure_complexity.py` alive for one consumer contradicts "one implementation per concern." The shell-out rewrite is the cleaner fix and costs a small script rewrite.
- **Confidence:** High. Both are file reads, not inference.

### F6 · High · UPGRADE — The orchestrator is the last thing built, so the parts under review are the parts least likely to exist

- **Where:** "Build order," which inherits the prior plan's nine steps and inserts `python-architecture` between 6 and 7.
- **What:** `python-workflow` — recipes, checkpoints, evidence-conditioned skipping, soft-dep probing — is step 9 of 10. Every distinguishing claim in this document lives there. Steps 2 through 8 produce individually useful skills and zero pipeline.
- **Why it matters:** This is a solo project done intermittently. The realistic outcome of a ten-step order is four steps done and six queued, which means you end with a slightly better version of what you have now — a pile of Python skills — and the orchestration design, the actual subject of three rounds of review, never gets exercised once. The design cannot be wrong in a way you'd notice, because it never ran.
- **The probe:** Suppose you stop after step 4. What in this document has been tested against reality? Answer: the script consolidation and two merges. Not the recipes, not the checkpoints, not the skip logic, not the soft-dep probe.
- **The counter, stated fairly:** each step ships something usable, so nothing is wasted. True — but "usable" and "exercises the design" are different bars, and only the second one tells you whether the design is right.
- **Remedy:** Build a walking skeleton first. Insert a step 2a immediately after `python-scan`:
  > **2a. `python-workflow` — `critique` only.** `scan → report`. No `review`, no checkpoints (it is read-only), no skip logic. Verify: `python-workflow critique` runs end-to-end on a scratch project and writes zero files.

  Then each later skill lands *into* a working pipeline instead of into a queue, and `tidy` becomes reachable as soon as `python-patterns` and `python-quality-tools` exist (steps 3–4) rather than at step 9. You find out whether the recipe shape is right while it is still cheap to change.
- **Trades:** `python-workflow` gets touched three or four times instead of authored once. That is the cost of finding out early, and for a skill made of prose it is a small one.
- **Confidence:** Medium-High. Drops to Low if you intend to execute all ten steps in one sustained push — you know that and I don't.

### F7 · Medium · DEFECT — The Spec axis has no input in the use case this plugin exists for

**Where:** `python-review` cherry-pick table, "Two-axis Standards/Spec report shape; parallel sub-agent dispatch" — and the `python-review-lens` subagent profile that exists to serve it. `mattpocock/code-review/SKILL.md:72` already handles the missing-spec case: *"If the spec is missing, skip the Spec sub-agent and note this in the final report."* For "a finished script or module" there is no issue, no PRD, no `docs/agents/issue-tracker.md` — so the two-axis design runs one axis, the parallel dispatch has nothing to parallelize, and the profile is dispatched once. The prior plan raised exactly this objection (`plan.md:38-41`, "no fixed point and no spec. Wrong lens") and v2 re-imports the shape without re-answering it.
**Probe:** Run `critique` on a standalone module. What does the Spec lens compare against?
**Remedy:** Define the second axis for the specless case rather than inheriting one that skips — e.g. **Contract**: does the code do what its own docstrings, names, and type hints claim? That keeps two lenses firing in the primary use case, gives `python-review-lens` a reason to exist, and is a natural slot for F4's architecture lens as a third.

### F8 · Medium · DEFECT — `plugins/pythonista/agents/` cannot be produced by this build, and the codex precedent doesn't transfer

**Where:** "Mechanism note … no build-mechanism change needed for two static files." The premise is right (`build.py` has no `agents:` block) and the conclusion is wrong. `build_plugin` writes only `.claude-plugin/` and `skills/` (`build.py:709-711`); local skills come from repo-root `skills/<name>/`, and no source path reaches `plugins/pythonista/agents/`. `plugins/codex/agents/` exists only because `vendor:` returns early at `build.py:707` before any of that dispatch — a vendored plugin owns its whole tree. So the options are a real `agents:` block in `build.py`, or hand-maintained files inside a generated directory, which `CLAUDE.md` and the prior plan's non-negotiables both forbid ("Never hand-edit anything under `plugins/`").
**Probe:** Trace a source path that lands a file at `plugins/pythonista/agents/python-review-lens.md`. There isn't one.
**Remedy:** Given F7 leaves one profile without a justification, cut the subagent section to a deferred note: "Two profiles are worth building once `python-review` has two lenses that fire; both require an `agents:` block in `build.py` mirroring `skills:` — a real build change, not two static files." Note also that `skillcraft/skills/agent-development` exists and is the more natural authority than `codex-rescue.md` for house style.

### F9 · Medium · DEFECT — Retiring `code-review-excellence` contradicts the reasoning used to keep `git-commit`

**Where:** the `python-review` table ("propose retiring it from `codementor` once harvested") versus the `git-commit` paragraph, which keeps that skill in `codementor` partly because it is "genuinely reusable if a second language pack is ever added." The severity taxonomy being harvested (blocking/important/nit/suggestion/learning/praise) is exactly as language-agnostic as `git-commit`, and `codementor`'s stated purpose covers "code review hygiene." Two paragraphs apply opposite reasoning to two equally agnostic skills in the same plugin, and one of them ends in a deletion.
**Probe:** State the property that makes `git-commit` worth keeping for a hypothetical future JS pack but `code-review-excellence` worth deleting.
**Remedy:** Drop the retirement proposal. Harvest the taxonomy into `python-review` and leave `code-review-excellence` where it is, on the same reasoning already written for `git-commit`. Removes an irreversible action from the plan for the cost of one plugin entry.

### F10 · Medium · DEFECT — `critique`'s optional deep lane has no one who can start it

**Where:** the `critique` diagram (`└─optional─▶ python-architecture`) against two rules that bracket it — `critique` is "[read-only, 0 checkpoints]" and `python-architecture` is "explicit call only, never auto-triggered … only the user *starts*." With no checkpoint in `critique`, there is no moment at which the user can elect the lane; with the never-auto-trigger rule, the agent cannot elect it either. The lane is unreachable as drawn.
**Probe:** Point at the step in the `critique` diagram where the deep lane is chosen.
**Remedy:** Delete the arrow. Have `critique`'s report end with a recommendation line — `architecture review recommended: run python-architecture` — which is consistent with both rules, preserves the intent, and costs a diagram edit. (If F4's lens option is taken instead, this resolves itself: the lens runs inside `python-review`.)

### F11 · Low · UPGRADE — The `python-workflow` rejection argues from the weaker of two available reasons

**Where:** "the shared machinery — checkpoint UI, soft-dep probing, 'establish state' — is real, load-bearing duplication if split." Skills are prose; three skills could each link one `references/checkpoints.md`, so the duplication argument is soft. The conclusion is right for a different reason.
**Probe:** Ask why three skills couldn't share a reference file. They could.
**Remedy:** Swap the reason: one skill because there must be exactly one entry point that can reach `git-commit`, and one description the model matches against — which is also what makes F1's read-only default enforceable. Same conclusion, an argument that doesn't fold.

## 4. Remediation plan

**Start here:** Rewrite the checkpoint block so each of the three stops names what it decides (F2). It is the root of the control model, F3's skip-approval lands inside checkpoint 1, and F1's read-only default is the same decision expressed in frontmatter — all three remedies are cheaper once the checkpoints mean something.

1. Rewrite the checkpoint block; give `ship-it`'s second stop a real branch and reclassify `tidy`'s terminal stop — fixes **F2**
2. Replace the evidence-conditioned paragraph with the skip table, moved to checkpoint 1; add the `python-scan` golden-test fixture — fixes **F3**
3. Add the three enforcement mechanisms: `disable-model-invocation` on the four deep-work skills, `critique` as the no-arg default, a read-only `python-workflow` description — fixes **F1**
4. Decide open item 1 on the corrected argument (output shape, not `CONTEXT.md`); choose skill-vs-lens — fixes **F4**
5. Split the last row of the `python-scan` table into three; port `analyze_all.py`, resolve `compare_metrics.py`'s imports — fixes **F5**
6. Insert build step 2a: `python-workflow` with `critique` only — fixes **F6**

7. Define the Contract axis so `python-review` has two lenses that fire without a spec — fixes **F7**
8. Cut the subagent section to a deferred note naming the `build.py` `agents:` block as its prerequisite — fixes **F8**
9. Drop the `code-review-excellence` retirement proposal — fixes **F9**
10. Delete the deep-lane arrow from the `critique` diagram; replace with a recommendation line — fixes **F10**

11. Swap the `python-workflow` rejection's reason — fixes **F11**

Order rationale: items 1–3 are one connected rewrite of the control model and should be done together; item 4 changes the inventory and item 5 changes the script partition, so both must settle before item 6 fixes the build order that depends on them. Items 7 and 8 are coupled — cutting the subagent section is only correct while the second lens is undefined. Item 5 is the cheapest high-leverage work here: two file reads already done, and it prevents a crash at build step 7.

## 5. Swept, not raised

- **The three-checkpoint count.** Off-limits, and I would not have challenged it anyway — the read→write and reversible→irreversible boundaries are the right two axes. My quarrel in F2 is with what each stop decides, not how many there are.
- **Python-only, no agnostic core.** Off-limits, and the stated test ("a generic core only pays for itself with ≥2 language packs") is the correct test.
- **The `python-scan` / `python-quality-tools` split.** Survives. One wobble worth knowing: `check_documentation.py`'s output *does* have a fixer in this design — `python-document`. So "the analyzers have no `--fix` counterpart" isn't quite the criterion; the criterion is that the fixer is a different skill under a different tier. Didn't raise it because the decision is right on either framing.
- **`python-patterns` absorbing `python-simplifier` wholesale.** Survives. Idioms/dead code/duplication/YAGNI genuinely are one assessment against a quality bar.
- **Open item 3's diagnosis — verified true.** `python-performance-optimization/SKILL.md` has "When to Use / Core Concepts / Quick Start / Analysis Scripts / Choosing a Profiler / Best Practices / Common Pitfalls / Script Reference" and no `## Workflow` section, while `python-testing-patterns/SKILL.md:49` has an explicit numbered "Workflow: Testing Code That Already Exists." Fold it in — the diagnosis is correct and the gate it proposes is the one the chatgpt source asked for.
- **`find_code_smells.py`, left "Undetermined."** Deferring is fine, but here is the answer so you don't re-derive it: it detects magic numbers, bare excepts, mutable defaults, type comparisons, god classes, data classes, long parameter lists. Mutable defaults and type comparisons are B006/E721 — already routed to ruff by your own affaan-m row. God classes and long parameter lists are the part worth keeping.
- **Reusing refactor's threshold table.** Right call, no note — see F3 for using it more consistently.
- **`git-commit` staying in `codementor`.** Agreed; the compound-dependency distinction is real and the plugin-purpose argument is sound. See F9 only for the inconsistency it creates elsewhere.
- **`python-patterns` running before `python-quality-tools` in both mutating recipes**, where both can touch dead code and unused imports. Not raised: checkpoint 1's approved plan makes both stages visible before either runs, so the overlap is a human-visible ordering choice rather than a hidden one.
- **Recipe names, the layer diagram, harvest-don't-vendor, the codex-rescue house style.** All fine. The house-style call is right; see F8 only for the more natural authority.

## 6. Where this review could be wrong

- **The `beagle` and `affaan-m` claims are the one thing I could not check.** Neither appears in `bundles.yaml` or the tree — prior plan step 1 ("fetch and read") has not run. Every claim about beagle's Scope→false-positive→Evidence→Verification→Ship gate, and about affaan-m's idiom categories and anti-patterns table, is untested by me. If beagle's gate is weaker than described, `python-review`'s "the actual prize" attribution moves.
- **F6 is a judgment about your own follow-through, not about the document.** If you intend to build all ten steps in one push, it is noise — you know that and I don't.
- **F2 assumes the never-auto-trigger rule is strict.** If you always intended `ship-it` to be able to launch deep work with consent, then checkpoint 2 is fine and only its wording is wrong, which downgrades F2 to Low.
- **F4's lens recommendation depends on invocation frequency.** If you would genuinely reach for architecture review standalone and often, the twelfth skill is right and only the argument needs replacing.
- **I verified against the copies vendored in this worktree.** Upstream may have moved since they were fetched; `mattpocock/code-review:72` and `improve-codebase-architecture:68` are the two lines F7 and F4 rest on.
- **I did not assess whether Claude Code supports an `agents/` directory at plugin root at all** — only that `build.py` cannot produce one. If the runtime doesn't read it either, F8 gets larger, not smaller.
