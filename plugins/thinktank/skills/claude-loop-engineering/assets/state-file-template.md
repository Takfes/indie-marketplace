# Loop state — <PROJECT / LOOP NAME>

> The spine of the loop. The model forgets everything between runs; this file is the memory that lives on disk. Each run reads it first and updates it last. Keep it terse and machine-greppable. The agent forgets; this file doesn't.

## Mission
<One sentence: what this loop exists to do and its verifiable definition of "done overall.">

## Guardrails (read every run, do not violate)
- May touch: <paths / branches>
- Must not touch: <protected paths, main branch, etc.>
- Budget: <max turns / time / token or dollar ceiling per run>
- Escalate (stop + log below, never auto-merge) when: <stuck after N tries / risky change / ambiguous spec>

## Now (in flight)
- [ ] <current unit of work> — worktree: <path/branch> — started: <date>

## Next (queue)
- [ ] <item> — source: <issue # / CI failure / TODO>
- [ ] <item>

## Done (newest first)
- [x] <item> — PR: <link> — verified by checker: <yes/no> — <date>

## Escalated to human (needs your call)
- ⚠ <what happened, what the loop tried, why it stopped> — <date>

## Run log
- <date/time> — cycle summary: found <n>, drafted <n>, passed checker <n>, opened <n> PRs, escalated <n>.
