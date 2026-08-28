---
name: python-review
description: >
  Judgment-based critique of Python code, beyond what python-scan's deterministic
  analyzers catch. Dispatches two parallel review lenses — Standards (Fowler code
  smells plus any repo-documented conventions, which always override the
  baseline) and Contract (does the code do what its own docstrings, names, and
  type hints claim?) — each finding gated by an anti-confabulation re-read and
  FILE:LINE evidence before it ships. Runs against a diff since a fixed point,
  or a standalone finished module with no spec to compare against (the common
  case in this plugin). Use for a judgment pass on a module, script, or PR;
  feeds python-workflow's critique recipe.
---

# Python Review

Layer 1 (judgment) of the pythonista pipeline, sitting directly on top of `python-scan`'s
deterministic layer 0. Where `python-scan` finds only what an AST walk can prove, this skill
finds what requires reading and comparing: does this code follow how the repo is documented to
be written, and does it actually do what it claims to do?

Read-only, always. Never edits a file, never proposes running a mutating tool — only produces a
report.

## When to Use This Skill

- A judgment pass on a finished module, script, or PR that goes beyond `python-scan`'s mechanical
  checks
- Invoked directly by name, or as the `review` stage of `python-workflow`'s `critique` recipe
  (`scan -> review -> report`)
- Reviewing a diff since a fixed point ("review since main", "review this PR") or a standalone
  file/directory with nothing to diff against

## Mode: pick one before dispatching

Runs in exactly one of two modes per invocation:

| Mode | When | What "the code under review" means |
|---|---|---|
| **Diff** | The user names a fixed point (commit, branch, tag, `main`, `HEAD~5`) or asks to "review since X" | `git diff <fixed-point>...HEAD` (three-dot, against the merge-base) |
| **Module** | The user names a path with no fixed point — a finished script, file, or directory | The file(s) at that path, as they stand |

Diff mode: confirm the fixed point resolves (`git rev-parse <fixed-point>`) and the diff is
non-empty before dispatching — a bad ref should fail here, not inside two parallel subagents.
Also capture `git log <fixed-point>..HEAD --oneline` for commit context, and pass both to the
Standards subagent.

Module mode is the primary case this plugin exists for, and the reason a second axis exists at
all: a standalone script has no issue, PRD, or spec to check against.

## The two axes

Always both, in every mode — this is what makes module mode work. Unlike a Spec axis, which
would run empty with nothing to compare against, both axes below always have real input to
check.

### Standards

Does the code conform to how this repo says code should be written?

1. Look for anything the repo documents: `CODING_STANDARDS.md`, `CONTRIBUTING.md`, project
   `CLAUDE.md`/`AGENTS.md` files scoped to the reviewed path.
2. On top of whatever's documented, Standards always carries the smell baseline below — a fixed
   set of Fowler code smells (*Refactoring*, ch. 3) that applies even when the repo documents
   nothing.

Two rules bind the baseline:

- **The repo overrides.** A documented repo standard always wins — where it endorses something
  the baseline would flag, suppress the smell.
- **Always a judgement call.** Each smell is a labelled heuristic ("possible Feature Envy"),
  never a hard violation. Skip anything tooling (ruff/mypy) already enforces — that's
  `python-quality-tools`'s job, not this skill's; don't duplicate it.

**Smell baseline** (reads *what it is* → *how to fix*; match against the reviewed code):

- **Mysterious Name** — a function, variable, or type whose name doesn't reveal what it does or holds. → rename it; if no honest name comes, the design's murky.
- **Duplicated Code** — the same logic shape appears more than once in the reviewed code. → extract the shared shape, call it from both.
- **Feature Envy** — a method that reaches into another object's data more than its own. → move the method onto the data it envies.
- **Data Clumps** — the same few fields or params keep travelling together (a type wanting to be born). → bundle them into one type, pass that.
- **Primitive Obsession** — a primitive or string standing in for a domain concept that deserves its own type. → give the concept its own small type.
- **Repeated Switches** — the same `if`/`match` cascade on the same type recurs. → replace with polymorphism, or one map both sites share.
- **Shotgun Surgery** *(diff mode only — needs edits scattered across files to detect)* — one logical change forces scattered edits across many files. → gather what changes together into one module.
- **Divergent Change** — one file or module holds responsibility for several unrelated reasons. → split so each module changes for one reason.
- **Speculative Generality** — abstraction, parameters, or hooks added for needs nothing in the code or its docstrings asks for. → delete it; inline back until a real need shows.
- **Message Chains** — long `a.b().c().d()` navigation the caller shouldn't depend on. → hide the walk behind one method on the first object.
- **Middle Man** — a class or function that mostly just delegates onward. → cut it, call the real target direct.
- **Refused Bequest** — a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance, use composition.

### Contract

Does the code do what its own docstrings, parameter/return names, and type hints claim it does?
This is the axis that always fires in module mode — every function that documents or types
itself makes a checkable claim, spec or no spec.

Check, for each public function/method/class in scope:

- Does the docstring's stated behavior match what the body actually does (return value, side
  effects, error conditions raised vs. documented)?
- Do the parameter and return type hints match what's actually passed/returned at runtime, as
  far as static reading can tell?
- Does the name itself make a claim the body breaks (`get_user` that also mutates state,
  `is_valid` that raises instead of returning a bool)?
- Documented `Raises:` entries — are they the exceptions the body can actually raise, no more,
  no fewer?

An undocumented, untyped function makes no claims and gives Contract nothing to check against —
that's a Standards-axis/`python-document` concern (missing docs), not a Contract violation.
Contract only fires against a claim that's actually there.

## Dispatch

Spawn **two parallel** Agent-tool subagents, `subagent_type: "general-purpose"` (not `"fork"` —
independence is the point, the same reasoning `adversarial-review` uses), one per axis:

- Model: `sonnet` by default for both. Escalate either to `opus` when the reviewed code is large,
  architecturally tangled, or judgment-heavy enough that a sharper model changes the outcome.
- Each subagent's prompt must include: the mode (diff command + commit list, or the module
  path(s)), the standards-source files found above pasted in full (Standards agent only), and
  this line: "Read `<SKILL_DIR>/references/review-protocol.md` and follow it exactly — gate 0
  first, then gates 1-5, using the tables in that file. Score every surviving finding's
  confidence 0-100. Report under 400 words."
- Substitute the real absolute path for `<SKILL_DIR>`. Having the subagent read the protocol
  itself, rather than pasting it into the dispatch prompt, keeps prompts lean and guarantees the
  full ruleset reaches it.
- If `python-scan` has already run this pass (e.g. inside `python-workflow`'s `critique`
  recipe), pass its JSON report to both subagents with this instruction: "Do not re-report
  anything in this report's `categories` — it's already known. Find judgment beyond it." This is
  what keeps Standards/Contract from duplicating `python-scan`'s mechanical findings (mutable
  defaults, `==True`, bare `except` — all ruff-coverable, already routed to
  `python-quality-tools`).

## Confidence filter and second pass

Each finding a subagent returns carries a 0-100 confidence score. Drop anything under 80 before
it reaches aggregation — this is the false-positive filter, on top of (not instead of) gate 0.

Before the report ships, run a **second, independent pass** over every finding that survived the
80 threshold: re-open the cited `file:line` yourself, fresh, and re-run gate 0
(`references/review-protocol.md`) against it. This is deliberately not the same read the axis
subagent already did — it's the second, independent defense `anthropics/claude-code`'s own
`code-review` plugin uses (dispatch to find, then a separate pass to validate each flagged
issue) before a finding is allowed to ship. If a finding doesn't survive your own fresh re-read,
drop it and say so — don't keep it just because a subagent already vouched for it.

For an unusually large finding set, dispatch a dedicated validation subagent per finding instead
of doing this pass yourself — same rule, different execution; use judgment on when the volume
warrants it.

## Severity

Two things travel with every finding: a **calibration bucket**, from
`references/review-protocol.md`'s Severity Calibration, which decides whether the finding is
included at all and whether it counts toward the actionable total; and a **presentation label**,
shown to the user:

| Calibration bucket | Label |
|---|---|
| Critical | 🔴 `[blocking]` — must fix |
| Major | 🟡 `[important]` — should fix, discuss if you disagree |
| Minor | 🟢 `[nit]` (style/clarity) or 💡 `[suggestion]` (alternative approach) — your call which fits |
| Informational | 📚 `[learning]` — noted for awareness, never counted toward the actionable total |
| *(not a finding)* | 🎉 `[praise]` — call out something done well; not gated by calibration, doesn't count for or against anything |
| Do NOT Flag At All | — dropped before gate 3, never reaches the report |

## Aggregate

Present the two subagent reports under `## Standards` and `## Contract` headings, lightly
cleaned. Do **not** merge or re-rank findings across axes — they're deliberately separate (see
*Why two axes*, below). Every finding: `[FILE:LINE]`, the taxonomy label, a one-line description,
a fix hint where one exists.

End with a one-line summary per axis: total actionable findings (Critical/Major/Minor —
Informational never counts) and the worst issue *within that axis*, if any. Don't pick a single
winner across axes — that's the re-ranking the separation exists to prevent.

## Why two axes

- Code that follows every standard but claims something its body doesn't do → **Standards pass,
  Contract fail.**
- Code that does exactly what its docstring promises but breaks the project's conventions to get
  there → **Contract pass, Standards fail.**

Reporting them separately stops one axis from masking the other — the same reasoning
`mattpocock/code-review` uses for its original Standards/Spec split, carried over here to
Standards/Contract.

## Explicit boundaries

- Never mutates a file, never proposes running a mutating tool — a report only.
- Never re-reports what `python-scan` already flagged when a scan report was supplied to it —
  see Dispatch, above.
- Never skips gate 0 for a finding, regardless of how confident a subagent already sounds.
- Never ships a finding under confidence 80, and never ships one that failed the second pass's
  fresh re-read.
- Diff mode requires a resolvable fixed point with a non-empty diff, confirmed before dispatch.

## Reference file

`references/review-protocol.md` — gate 0, gates 1-5, the hard-gates table, Valid Patterns,
Context-Sensitive Rules, per-issue-type verification recipes, and Severity Calibration. Both
dispatched subagents read this themselves (see Dispatch, above); you don't need to unless you're
tuning the skill.
