# Loop patterns

Six proven shapes. Each lists when to use it, the trigger primitive, the full assembly (the six pieces from SKILL.md), guardrails specific to the pattern, and an example. Adapt — don't copy blindly. Match the pattern to the user's Step-1 spec.

---

## 1. Goal-to-green
**When:** a well-defined task with a verifiable finish line, done in one sitting while the user is around. Migrations, "implement this design doc until acceptance criteria hold," "split this file until each module is under N lines."

**Trigger:** `/goal`.

**Assembly:** mostly just a sharp condition + (optional) a checker subagent for quality the machine check misses. State file optional for a single sitting.

**Guardrails:** condition must be provable from Claude's own output; include `or stop after N turns`; turn on auto mode so turns run unattended; pair the machine check with a quality assertion if correctness isn't fully mechanical.

**Example:**
```text
/goal Every call site of the old PaymentsClient is migrated to PaymentsClientV2,
`npm test` exits 0, lint is clean, and no test file is modified — or stop after 25 turns.
```

**Failure mode to avoid:** a verification-only condition can pass every machine check and still ship something embarrassing (the classic: a game that passes headless playtests but renders a triangle and three pixels). When the output has a quality dimension a test can't catch, write that dimension into the condition or hand it to a checker subagent.

---

## 2. Morning triage (discovery loop)
**When:** "every morning, look at what changed and surface what's worth doing." The canonical loop.

**Trigger:** Desktop or Cloud **scheduled task** (durable; runs with laptop closed). `/loop 1d` only if a session stays open.

**Assembly:**
- Trigger calls a **triage skill** that reads yesterday's CI failures, open issues, and recent commits.
- Writes findings to the **state file** (or a Linear board via MCP).
- For each finding worth doing, opens an isolated **worktree** and dispatches a **maker subagent** to draft a fix; a **checker subagent** reviews against tests + project skills.
- **Connectors** open the PR and update the ticket; anything unhandled lands in the inbox/state file for the human.

**Guardrails:** loop opens PRs, never merges; stuck items escalate to the inbox; cost ceiling via cheap model for triage, stronger model only for the checker.

**Example (conversational, in Desktop):** *"Set up a task every weekday at 8am that runs my triage skill, opens a worktree per actionable issue, drafts a fix with a subagent, has a checker subagent verify it against tests, and opens a draft PR — anything it can't handle, write to TRIAGE_INBOX.md and stop."*

---

## 3. Backlog burndown
**When:** work a labeled queue (issues, TODOs, flaky tests) until it's empty.

**Trigger:** `/goal` for a supervised sitting, or a **scheduled task** to chip away daily.

**Assembly:** discovery = the labeled queue; unit of work = one item; **state file** tracks done/in-flight/blocked; maker/checker per item; worktree per item.

**Guardrails:** condition = "the `agent-ready` label queue is empty or only blocked items remain"; bound by turns; each item is its own PR for reviewable diffs.

**Example:**
```text
/goal Work the GitHub issues labeled `agent-ready`: for each, open a worktree, draft a
fix, have the checker subagent verify tests pass, open a PR, and remove the label.
Stop when the queue is empty or every remaining item is blocked — or after 15 issues.
```

---

## 4. Watch-and-fix (polling)
**When:** babysit a long-running thing — CI, a deploy, a migration job, sub-agent progress — and react when state changes.

**Trigger:** `/loop <interval>` (in-session).

**Assembly:** light. The prompt/skill checks state each tick and acts or reports. State file optional.

**Guardrails:** keep the interval sane (seconds round to a minute); remember it dies with the session — use a scheduled task if it must survive; cap with the 3-day `/loop` limit in mind.

**Examples:**
```text
/loop 5m /babysit       # address review comments, rebase, shepherd open PRs
/loop 10m check if the staging migration finished and summarize what happened
/loop 15m check whether any subagent tasks completed and roll up their results
```

---

## 5. Parallel batch migration
**When:** the same mechanical change across hundreds of files/sites — too big for one conversation to coordinate.

**Trigger:** **dynamic workflow** (Claude writes a JS orchestration script), or a manual fan-out of worktree-isolated subagents.

**Assembly:** classifier/explorer agent maps the work; many maker subagents run in parallel, **each in its own worktree**; checker stage verifies; results converge to a single summary in your context.

**Guardrails:** runtime caps (16 concurrent / 1,000 total) exist to stop runaways — stay well under; pick a cheap model per worker, stronger for verification; every worker tests its own change end-to-end before opening a PR; review bandwidth is the real ceiling.

**Example (conversational):** *"Migrate all synchronous IO to async across the repo. Batch the changes, launch parallel agents with worktree isolation, each tests its changes end to end, then opens a PR."*

---

## 6. Maker/checker review loop
**Not a standalone loop — the trust core you fold into the others.** Any loop that runs unattended needs the agent that writes separated from the agent that grades, because a model grading its own work is too generous.

**Assembly:** `.claude/agents/maker.md` (implements; can write) + `.claude/agents/checker.md` (verifies; strong model, read-oriented tools, runs tests, checks diff against spec + skills). The usual triad: one explores, one implements, one verifies. This is also what `/goal` does under the hood — a fresh model decides "done," not the one that did the work.

**Guardrails:** checker gets a different (often stronger) model; least-privilege tools; its verdict is PASS/FAIL with specific evidence, not vibes. Templates: `assets/maker-subagent-template.md`, `assets/checker-subagent-template.md`.

---

## Composing patterns
Real setups stack these: a **morning-triage** scheduled task whose per-item work is a **backlog-burndown** `/goal`, with a **maker/checker** core and a **watch-and-fix** `/loop` shepherding the resulting PRs to green. Start with one pattern, supervised, then compose once each piece is trustworthy.
