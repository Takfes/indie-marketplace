---
name: loop-engineering
description: Design and scaffold autonomous "loops" in Claude Code — systems that find work, act on it, verify the result, and decide the next step, instead of you hand-prompting each turn. Use this whenever the user wants to automate a recurring dev workflow, set up a bot that triages/fixes/reviews on a schedule, run an agent "until tests pass" or "while I sleep," burn down an issue backlog autonomously, batch a large migration across many files, or wire up /goal, /loop, scheduled tasks, Stop hooks, subagents, or worktree isolation into a repeatable harness. Trigger this even when the user doesn't say "loop" — phrases like "automate this," "run this every morning," "keep going until it's done," "make it self-running," "set up a triage/review bot," or "have an agent fix CI failures on its own" all mean a loop. Prefer this skill over ad-hoc advice because a loop that ships unattended needs verification, isolation, and cost guardrails designed in from the start, and this skill encodes that.
---

# Loop Engineering

## What this is

A **loop** is a recursive goal: you define a purpose and a stopping condition, and an agent iterates — find work, act, observe the result, decide the next move — until the condition holds or it escalates back to you. Loop engineering is the shift from *prompting the agent* to *designing the system that prompts the agent*.

**The prime directive: you stay the engineer.** A loop running unattended is also a loop making mistakes unattended. The leverage point moves from writing prompts to designing verification, isolation, and stop conditions you actually trust. The same loop in good hands accelerates work the user understands deeply; in careless hands it manufactures comprehension debt at speed. Design accordingly — never hand someone a loop that lets them stop reading the code it ships.

Do not skip straight to writing commands. Work the steps below in order. Read `references/claude-code-primitives.md` for exact syntax before scaffolding anything, and `references/loop-patterns.md` to match the user's goal to a proven shape.

---

## Step 1 — Spec the loop before building it

A loop is only as good as its definition. Pin down these six things first; ask the user only for what you can't infer from the repo or conversation:

1. **Trigger** — what starts a cycle? A schedule (every morning), an interval poll (every 5 min while a job runs), a one-shot finish-line ("until tests pass"), or a large fan-out (migrate 400 files).
2. **Discovery** — how does the loop find work each cycle? (read CI failures, open issues, a labeled queue, a diff, a spec doc)
3. **Unit of work** — what does one iteration actually do? Keep it small and isolated.
4. **Done condition** — *verifiable* end state. Not "the code is good" but "`npm test` exits 0 and lint is clean." If you can't state it as something the agent's own output proves, the loop can't know when to stop. This is the single most important field.
5. **Escalation** — what does the loop do when it's stuck or hits something risky? (stop and write to an inbox/state file, open a draft PR for review, ping a channel) A loop with no escalation path silently does the wrong thing forever.
6. **Blast radius + budget** — what may it touch (which paths, which branches), and what's the ceiling (turns, time, tokens, dollars)?

If the user's done-condition is vague, that's the conversation to have — a verification-only condition produces output that passes every machine check and is still wrong. Pair machine checks with a quality assertion where it matters (see the games-PRD failure mode in the patterns reference).

---

## Step 2 — Choose the primitive(s)

Match the task shape to the Claude Code primitive. Full syntax and version requirements live in `references/claude-code-primitives.md`; this is the selection table.

| The user wants…                                              | Reach for            | Why |
| ------------------------------------------------------------ | -------------------- | --- |
| Work driven to a **verifiable finish line** in one sitting   | `/goal`              | Keeps working across turns; a fast checker model grades the condition after each turn and clears it automatically when met. |
| A prompt **re-run on a cadence** while a session is open     | `/loop <interval>`   | In-session polling (CI watch, shepherd a PR, check subagent progress). Dies when the session exits. |
| **Durable, unattended** runs (survive restart, laptop closed)| Scheduled task / routine | Desktop or Cloud scheduled task starts a fresh session on a cadence, with its own worktree + permission mode. |
| **Custom stop logic** after every turn, reused across sessions| Stop hook            | Script (deterministic) or prompt (model-judged) in settings; `/goal` is a session-scoped sugar over this. |
| **Massive parallel** fan-out (hundreds of files/agents)      | Dynamic workflow     | Claude writes a JS orchestration script; runs many subagents in the background, only the converged result hits your context. |
| **Maker/checker separation** within any of the above         | Subagents            | One agent writes, a different one (often a different model) verifies — the core trust mechanism. |

Most real loops **compose** these: e.g. a *scheduled task* that runs a *triage skill*, opens a *worktree* per finding, dispatches *maker + checker subagents*, and writes results to a *state file*. Pick the trigger primitive first, then layer the rest in Step 3.

---

## Step 3 — Assemble the six pieces

Every durable loop needs these. Missing pieces are exactly where loops leak. Templates for the file-based ones are in `assets/`.

1. **Automation / trigger** — the heartbeat (Step 2's primitive). Without it you have a one-shot, not a loop.
2. **Worktree isolation** — the moment more than one agent runs, unisolated file edits collide like two engineers editing the same lines. Use `git worktree`, the `--worktree` flag, or `isolation: worktree` in a subagent's frontmatter. Also a blast-radius control for risky refactors.
3. **Skills** — codified project knowledge (`SKILL.md` for conventions, build steps, "we don't do X because of that incident"). Without skills the loop re-derives your project from zero every cycle; with them, knowledge compounds. A *tight, boring* description triggers more reliably than a clever one.
4. **Connectors (MCP)** — let the loop touch real tools: issue tracker, database, staging API, Slack/channel. This is the difference between "here's the fix" and "opened the PR, linked the ticket, pinged the channel once CI was green."
5. **Maker + checker subagents** — keep the writer away from the grader; a model grading its own homework is too generous. Define them in `.claude/agents/*.md`; give the checker a strong model and read-only-ish tools. Use `assets/maker-subagent-template.md` and `assets/checker-subagent-template.md`.
6. **State file (the spine)** — the model forgets everything between runs, so memory must live on disk, not in context. A markdown file (or a Linear board via MCP) holding what's done, what's in flight, what's next, and what got escalated. Tomorrow's run picks up where today's stopped. Use `assets/state-file-template.md`. *The agent forgets; the repo doesn't.*

---

## Step 4 — Guardrails (non-negotiable)

Build these in from the start, not after the first runaway. State them explicitly to the user so they're choosing the trade-offs.

- **Verifiable stop condition** — already specced in Step 1; encode it literally in the `/goal` condition or Stop hook.
- **Bounds** — always include a turn/time clause (e.g. `or stop after 20 turns`). An impossible condition otherwise loops to the limit, burning tokens.
- **Cost ceiling** — sub-agents and long loops multiply token spend; usage varies wildly. Pick cheaper models for explore/verify where adequate, scope context with skills, and tell the user the rough cost shape.
- **Isolation** — worktree per parallel unit; least-privilege tools per subagent; consider `/sandbox` or a constrained permission mode for unattended runs.
- **Escalation path** — stuck or risky work stops and lands in the state file / inbox / draft PR, never auto-merges.
- **Human review gate** — unattended work opens PRs for review; it does not push to main unsupervised. The loop's "done" is a claim, not a proof.

---

## Step 5 — Build sequence

1. Write the **state file** first (it's the contract).
2. Create the **subagents** (maker, checker) in `.claude/agents/`.
3. Write or point to the **project skill(s)** the loop will lean on.
4. Wire **connectors** the loop needs (confirm which MCP servers are available).
5. Compose the **trigger** with everything above (the `/goal` condition, `/loop` command, or scheduled-task config).
6. **Dry-run small** — one finding, one file, visible (not unattended) — and watch a full cycle. Read what it produced.
7. Only after a clean supervised cycle, let it run on cadence / unattended, and **expand scope gradually**.

Never ship a loop straight to unattended-at-scale. The first run is supervised, on purpose.

---

## Anti-patterns to refuse or fix

- **Cron cosplay** — re-running a fixed prompt with no decision-maker inside is just a cron job. A loop chooses its next action from current state.
- **Verification-only conditions** — passes the machine check, ships garbage. Add a quality/visual assertion where correctness isn't fully mechanical.
- **Maker grades itself** — no separate checker means "done" means nothing.
- **No state file** — the loop forgets across runs and repeats or contradicts itself.
- **Unbounded goals** — no turn/time/cost clause; runs until the wallet stops it.
- **Unattended write-to-main** — escalate and open PRs instead.
- **Comprehension surrender** — if the loop exists so the user can stop understanding the work, you've built the wrong thing. Build it so they move faster on work they own.

---

## Reference material

- `references/claude-code-primitives.md` — exact syntax, semantics, and version requirements for `/goal`, `/loop`, scheduled tasks & routines, Stop hooks, subagents, worktree isolation, dynamic workflows, MCP connectors, auto mode, headless/`-p`. **Read before scaffolding.**
- `references/loop-patterns.md` — ready-to-adapt patterns (goal-to-green, morning triage, backlog burndown, watch-and-fix, parallel batch migration, maker/checker review) with full assembly and example commands.
- `assets/state-file-template.md`, `assets/maker-subagent-template.md`, `assets/checker-subagent-template.md`, `assets/stop-hook-example.md` — drop-in starting files to copy into the user's repo and adapt.

Build the loop. But build it like someone who intends to stay the engineer, not just the person who presses go.
