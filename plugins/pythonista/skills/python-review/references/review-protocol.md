# Review Protocol

Read this file in full before reporting a single finding. It is the shared rulebook for both
the Standards and Contract lenses — gate 0 first, then gates 1-5 in order, then the tables below
as you work each gate. Nothing here is optional and no gate may be skipped because the finding
"feels obviously right."

## Gate 0 — Anti-confabulation (runs before every other gate, every finding)

Before issuing **any** verdict — flag, reject, or downgrade a finding — echo the exact artifact
you are judging, quoted from a source you read **in this turn**:

- Code finding: the **file:line** plus the cited code, read freshly now, not recalled from
  earlier in this pass or from the branch/file name.
- Diff finding: the actual diff hunk under review.

> The artifact is the only source of truth. Never infer what you are reviewing from the branch
> name, the working directory, surrounding files, or recollection. If your mental model differs
> from the freshly read source, the source wins. A verdict issued without a same-turn echo of
> its target is invalid — emit the echo first, or do not emit the verdict.

This exists because a model under contextual priming will confidently flag code that isn't in
the file. It is the single most load-bearing rule in this document — every other gate assumes
gate 0 already passed for the finding it's checking.

## Gates 1-5 (reporting workflow)

Complete in order. Do not advance until each pass condition is met.

1. **Scope** — Pass: you list every file (or explicit glob) you inspected this run.
2. **False-positive screen** — Pass: for each issue you plan to report, you checked **Valid
   Patterns** and **Context-Sensitive Rules** below and dropped or narrowed anything those
   sections say not to flag.
3. **Evidence** — Pass: each remaining finding carries `[FILE:LINE]` (or a bounded line range).
   Symbols or short verbatim snippets may supplement the anchor, never replace it.
4. **Verification** — Pass: for each remaining finding, you ran the matching hard gate and
   per-issue-type recipe below, and assigned it a Severity Calibration bucket.
5. **Ship** — Pass: the write-up matches the report shape in `SKILL.md` — every finding still
   carries its confidence score, calibration bucket, and taxonomy label; nothing that failed a
   gate above made it into the draft.

If any gate fails for a finding, do not report it — gather more evidence or drop it. A dropped
finding is a correct outcome, not a shortfall.

## Hard gates, by finding type

Beyond gates 1-5 above, these apply to specific finding types before they may reach gate 3.

| Applies to | Pass condition |
|---|---|
| "Unused", "dead code", "never called", "orphaned export" | You ran a workspace-wide search for the symbol (grep/ripgrep or equivalent) and noted whether non-definition matches exist. If use may be dynamic (decorators, `getattr`, entry points, plugin registration), you state that and name the registration/import path that could justify it. |
| "Missing validation", "missing error handling", "race", "leak" | You checked at least one of: caller, route/middleware, parent task, framework hook, or lifecycle (teardown, `finally`, context-manager `__exit__`), and recorded whether responsibility already sits there. |
| Any finding | Full enclosing unit read — file path plus start-end line range or symbol name for the function/method/class you judged. A diff hunk alone, without reading the full enclosing unit, fails this gate. |

## Valid Patterns (do NOT flag)

Intentional, correct Python idioms — never report these as issues:

| Pattern | Why it's valid |
|---|---|
| Type annotation on a variable or return type | A hint for the type checker, not a runtime assertion — don't confuse with missing validation. |
| `Any` when interacting with an untyped third-party library | Required when the library ships no stubs. |
| Empty `__init__.py` | Valid package-structure marker, no code required. |
| `# noqa` comment | Valid when the linter rule genuinely doesn't apply to that line. |
| `typing.cast()` immediately after a runtime type check (`isinstance`, etc.) | Correct pattern to inform the type checker of an already-narrowed type. |
| `dict.get(key, [])` / `dict.get(key, default)` | Returns a default for a missing key — this is intentional handling, not error suppression. |
| `Optional[T]` / `T \| None` return type | The standard way to express "may be absent" in Python typing. |
| `assert` in test code | pytest rewrites assertions for diff output; this is pytest-native, not a missing exception. |
| `@pytest.fixture` with no explicit `scope` | Default `function` scope is correct for most fixtures. |
| `monkeypatch` over `unittest.mock` | Simpler, pytest-native API — not a downgrade. |
| A fixture returning mutable state | Each test gets a fresh invocation by default; this is not shared mutable state. |
| Lazy quantifier (`+?`, `*?`) in a regex | Deliberately prevents over-matching. |
| Multiple `return` statements in one function | Often improves readability (guard clauses); not itself a smell. |
| A comment explaining *why*, not *what* | Exactly what comments are for — never flag as noise. |

## Context-Sensitive Rules

Flag these **only** when every listed condition holds:

| Issue | Flag only if |
|---|---|
| Missing type annotation | Function is public (no leading `_`) **and** the type isn't obvious from context (`x = 5` is obviously `int`) **and** it's not a test function/fixture **and** the codebase otherwise types consistently. |
| Bare or overly generic `except` | Not inside a top-level error boundary / middleware **and** the caught exception is actually swallowed — not logged or re-raised — **and** specific exception types are knowable here **and** it isn't cleanup/teardown code where "catch anything" is the right shape. |
| Missing try/except | No middleware or higher-level handler catches this **and** the framework doesn't already handle it (e.g. FastAPI exception handlers) **and** the failure would crash rather than just fail one operation **and** the caller needs feedback specific to this error. |
| Unused variable | It lacks a leading `_` **and** it isn't referenced in an f-string, logging call, or debugger breakpoint. |

## Per-issue-type verification recipes

Run the matching recipe (in addition to the hard-gates table above) before a finding of that
type may pass gate 4.

**Unused variable/function** — Before flagging: search for all references (grep/workspace
search); check whether it's exported for external consumers; check whether it's reached via
decorator/`getattr`/plugin registration rather than a direct call; confirm it isn't a callback
handed to a framework (event hook, CLI entry point, pytest fixture). Common false positive:
a helper only reachable through dynamic dispatch that a static search under-counts.

**Missing validation/error handling** — Before flagging: check whether validation already
happens at a higher level (caller, decorator, framework layer); check whether the framework
already validates (Pydantic model, dataclass `__post_init__`, argparse type=); verify the
"missing" check isn't present in a different but equivalent form. Common false positive:
Pydantic/FastAPI already rejects the malformed input before the function body runs.

**Type assertion / unsafe cast** — Before flagging: confirm it's actually a cast, not a plain
annotation; check whether the type was already narrowed by a runtime check (`isinstance`,
`hasattr`) before this point; verify the framework doesn't already guarantee the type. A plain
`data: UserData = await load_user()` is an annotation, not an assertion — don't flag it as one.

**Resource/task leak** (unclosed file/connection, un-awaited or uncancelled asyncio task,
un-joined thread) — Before flagging: verify the cleanup genuinely doesn't exist anywhere
(context manager, `finally`, `atexit`, task-group scope) rather than just being in a different
function; confirm the code path can actually be reached without the cleanup running.

**Performance issue** — Before flagging: confirm the code runs often enough to matter (hot loop
vs. one-time setup); verify the fix would have measurable impact, not a micro-optimization;
check whether the standard library or framework already handles it efficiently. Do not flag:
object/comprehension construction in a function that runs once; algorithmic complexity on inputs
too small to matter without a stated scale requirement.

## Severity Calibration

Decides **whether** a finding is included at all — apply this after the hard gates and recipe
above, before assigning the taxonomy label in `SKILL.md`.

- **Critical** — only: security vulnerabilities (injection, auth bypass, data exposure), data
  corruption, a crash on the happy path, a breaking change to a public API/interface.
- **Major** — logic bugs that affect real behavior; missing error handling with a real user- or
  caller-visible impact; a performance issue with measurable impact; a genuine correctness gap
  between contract and behavior.
- **Minor** — clarity/naming, documentation gaps, inconsistent style within reason, non-critical
  test-coverage gaps.
- **Informational** — improvements that require adding a new dependency or module; suggestions
  for net-new code that didn't exist before (new abstractions, new test suites); architectural
  ideas for future consideration; optimizations with no measured impact in the current context.
  **These never count toward the actionable-finding total** — note them, but the verdict ignores
  them entirely.

**Do NOT flag at all** — drop before gate 3, never reaches the report: style preferences where
both approaches are valid; optimizations with no measurable benefit; test code not held to
production standards (intentionally simpler); vendored/generated/third-party code; hypothetical
issues that require unlikely conditions to trigger.

## Before shipping a finding

1. Re-read it and ask: did I verify this is actually an issue, in this pass, not from memory?
2. Can you point to the specific line that proves it, right now?
3. Would a domain expert agree this is a problem, or is it a style preference?
4. Does fixing it provide real value, or is it busywork?
5. Is this a fix to *existing* code, or a request for net-new code that didn't exist before? If
   the latter, it's Informational — see Severity Calibration above, not a blocking/important item.

If uncertain about any surviving finding: drop it, or mark it as an open question rather than a
verdict.
