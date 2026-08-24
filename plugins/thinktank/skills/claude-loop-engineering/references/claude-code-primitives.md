# Claude Code primitives for loops

Accurate syntax and semantics for the building blocks. Verify version requirements against the user's installed Claude Code (`claude --version`); features below note their minimums. When in doubt, check the official docs at code.claude.com/docs.

## Table of contents
- `/goal` — finish-line autonomy
- `/loop` — cadence polling in-session
- Scheduled tasks & routines — durable unattended runs
- Stop hooks — custom per-turn evaluation
- Subagents — maker/checker, isolated contexts
- Worktree isolation — parallel without collisions
- Dynamic workflows — massive parallel fan-out
- MCP connectors — touch real tools
- Auto mode, sandbox, headless

---

## `/goal` — keep working toward a verifiable condition
Requires Claude Code v2.1.139+. One goal active per session.

`/goal` sets a completion condition; Claude keeps working across turns without you prompting each step. After every turn a small fast model (defaults to Haiku) checks whether the condition holds, returns yes/no plus a short reason; "no" feeds the reason back as guidance for the next turn, "yes" clears the goal automatically.

```text
/goal all tests in test/auth pass and the lint step is clean
```

- Setting a goal starts a turn immediately — no separate prompt needed.
- The evaluator judges the condition against what Claude has **surfaced in the conversation**; it does not run commands or read files itself. So write conditions the agent's own output can demonstrate (e.g. "`npm test` exits 0" — because Claude runs it and the result lands in the transcript).
- A good condition has: one measurable end state, a stated check (how to prove it), and constraints that must not change ("no other test file is modified").
- **Bound it**: include a clause like `or stop after 20 turns`. Max 4,000 chars.
- `/goal` alone = status (turns, tokens, last reason). `/goal clear` (aliases: stop/off/reset/none/cancel) ends it early. `/clear` also removes it.
- Resumes with `--resume`/`--continue` (condition carries over; timer/turn/token baselines reset).
- Headless: `claude -p "/goal CHANGELOG.md has an entry for every PR merged this week"` runs to completion in one invocation; Ctrl+C interrupts.
- Internally a session-scoped prompt-based Stop hook. Requires accepting the workspace trust dialog; unavailable if `disableAllHooks` or `allowManagedHooksOnly` is set.

## `/loop` — re-run a prompt on a cadence
In-session scheduler. Schedules a recurring task locally for up to 3 days at a time; **dies when the session exits.** Backed by the agent's own `CronCreate`/`CronList`/`CronDelete` tools.

```text
/loop 5m /babysit            # auto-address review comments, rebase, shepherd PRs
/loop 30m /slack-feedback    # auto open PRs for Slack feedback
/loop 15m check if any subagent tasks have completed and summarize
```

- Interval units: `s`, `m`, `h`, `d`. Seconds round up to 1 minute (cron has 1-min granularity). Odd intervals (7m, 90m) round to a clean value; Claude tells you what it picked. Interval can lead, trail, or be omitted.
- Use for: watching a long job, polling CI, shepherding PRs, a parent agent checking on subagent progress.
- Stops when you stop it or Claude decides the work is done.

## Scheduled tasks & routines — durable, unattended
Two flavors:
- **Desktop scheduled tasks** — survive restarts, fire on a visible schedule, run while the app is open. Each due task starts a *fresh* session independent of current work, with a deterministic stagger (up to ~10 min). Controls: model, permission mode, working folder, **worktree toggle** (isolate each run from your manual edits).
- **Cloud scheduled tasks / routines** — run on Anthropic infrastructure, persist across restarts, execute even when your machine is off.

Create conversationally in a Desktop session: *"set up a daily code review that runs every morning at 9am"* or *"schedule a task to run all tests every 6 hours."* For intervals the picker lacks (every 15 min, first of month), just ask in plain language. Wire output to Channels (Telegram/Discord) so findings land on your phone.

Use when the loop must run with the laptop closed or survive restarts — the right choice for true "while I sleep" automation. (`/loop` is the wrong tool there; it's session-scoped.)

## Stop hooks — custom evaluation after every turn
Live in your settings file; apply to every session in scope (unlike `/goal`, which is session-only). Two kinds:
- **Script (deterministic)** — run a command; exit code decides. Preferred for auditable workflows.
- **Prompt-based (model-judged)** — a prompt evaluates whether to stop.

Reach for a Stop hook when you want the same completion logic across sessions or logic too custom for a `/goal` condition. Configurable via `settings.json`; respects `disableAllHooks` / `allowManagedHooksOnly`.

## Subagents — isolated contexts, maker/checker
Defined as markdown with frontmatter in `.claude/agents/`. Each runs in its **own context window** with its own prompt, tool access, and permissions; only a summary returns to the main thread (keeps context clean for verbose explore/verify work).

```markdown
# .claude/agents/checker.md
---
name: checker
description: Verify a change against the spec and tests. Read-only review.
model: opus            # checker gets the strong model
isolation: worktree    # run in a throwaway git worktree
---
You verify, you do not write code. Run the tests, read the diff against the
spec and project skills, and report PASS/FAIL with specific evidence...
```

- Claude delegates when a task matches a subagent's `description`.
- Give the checker a strong model + minimal (read-oriented) tools; the explorer can be a fast cheap model.
- Subagents cost extra tokens (own model + tool work) — spend them where a second opinion pays for itself.
- Compare parallelization options (subagents, agent view, agent teams, worktree sessions) at code.claude.com/docs/en/agents.

## Worktree isolation — parallel without chaos
A `git worktree` is a separate working directory on its own branch sharing the same repo history, so one agent's edits can't touch another's checkout. Three ways in:
- `git worktree` manually, or the `--worktree` flag to open a session in its own checkout.
- `isolation: worktree` in a subagent's frontmatter — fresh checkout per helper, self-cleaning.
- The worktree toggle on a scheduled task.
- Non-git VCS (Mercurial/Perforce/SVN): define `WorktreeCreate`/`WorktreeRemove` hooks in `settings.json` for the same isolation.

You are still the ceiling — review bandwidth, not the tool, caps how many you can run.

## Dynamic workflows — orchestrate subagents at scale
Requires v2.1.154+; paid plans (on Pro, enable via the Dynamic workflows row in `/config`). Claude writes a **JavaScript orchestration script** for a task you describe; a runtime executes it in the background while your session stays responsive. Intermediate traces stay in script variables and never hit your context — only the converged result returns.

- Use for: codebase-wide bug sweep, 500-file migration, cross-checked research, drafting a hard plan from several independent attempts.
- Runtime caps: 16 concurrent agents (fewer on limited CPU), 1,000 agents total per run, to prevent runaway loops. Resumable within the session (completed agents return cached results).
- Can choose each agent's model and whether it runs in its own worktree.
- "Ultracode" setting = xhigh reasoning + automatic workflow orchestration (Claude plans a workflow per substantive task without being asked; uses more tokens/time).

## MCP connectors
Both Claude Code and Codex speak MCP, so a connector written for one usually works in the other. Connectors let the loop read the issue tracker, query a DB, hit a staging API, post to Slack. Bundle connectors + skills as a **plugin** so a teammate installs the whole setup in one go. Confirm which MCP servers the user actually has connected before designing a loop that depends on one.

## Auto mode, sandbox, headless
- **Auto mode** — approves tool calls within a turn (removes per-tool prompts); complementary to `/goal` (which removes per-turn prompts). Needed for `/goal` turns to run truly unattended.
- **`/sandbox`** — Claude Code's open-source sandbox runtime; file + network isolation, fewer permission prompts. Good for unattended/risky loops.
- **Headless / `-p`** — non-interactive runs for CI and GitHub Actions; combine with structured-output flags for parseable, fully automated runs with no approval prompts.
- **ralph-wiggum** community plugin — a known pattern for very long-running uninterrupted tasks.
