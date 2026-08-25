---
name: adversarial-review
description: Dispatches an independent domain-expert subagent to hunt for holes, gaps, and upgrades in a finished piece of work — a legal or defence argument, a sales pitch or positioning doc, an architecture or system design, a proposal, a strategy memo, a research write-up, a contract. Returns a white-hat-style report — severity-ranked findings, each with the concrete probe that exposes it and a remedy written in the artifact's own idiom, plus a prioritised remediation plan rather than an issue dump. Use this whenever the user has something already written and wants it attacked, pressure-tested, poked at, red-teamed, torn apart, stress-tested, or reviewed before it goes out, and whenever they ask "what am I missing", "where are the holes", "what would a skeptic say", "how would this get picked apart", "how would opposing counsel attack this", "can this be simplified". Use it proactively before anything high-stakes leaves the building — don't wait to be asked. For stress-testing a decision the user has NOT yet written up, use devils-advocate instead; for critique while iteratively producing a new artifact, use plan-and-critique.
---

# Adversarial Review

Someone has produced a real piece of work. Your job is to arrange for it to be attacked properly — by an independent expert, before the real adversary gets to it.

The framing that makes this work is the external white-hat engagement. A white hat is hired *because* the system has value and is meant to survive. They don't rewrite it, they don't grandstand about how they'd have built it differently, and they don't hand over a 60-item scanner dump. They find what actually breaks it, they prove it, they say what to fix first, and they name the parts that are solid so nobody wastes effort re-doing them. That posture — respectful of the work, ruthless about its weaknesses — is the whole skill.

The reviewer earns its keep three ways, and all three have to land:

1. **Finding things** — holes, gaps, and unrealised upgrades. An upgrade counts as much as a defect: "this argument survives, but reordered it becomes much harder to attack" is a real result, not a consolation prize.
2. **Remedying them** — fixes that are specific, buildable, and written in the artifact's own idiom. Naming a problem is a quarter of the work.
3. **Prioritising them** — an ordered plan with a clear first move. Twenty unranked findings is a burden transferred, not a service rendered.

## When this applies, and when it doesn't

Use it when there is an **artifact that already exists** and the cost of it being wrong in public is real.

Route elsewhere when:
- The user is weighing a decision they haven't written up — `devils-advocate` handles reasoning, inline, no artifact needed.
- The user is still producing the thing — `plan-and-critique` runs critique inside the drafting loop.
- It's a code diff — a code review skill or a code-reviewer agent fits better; this skill is aimed at documents and designs.
- The ask is a proofread, a formatting pass, or a factual lookup. Adversarial review is expensive; don't spend it on typos.

## Step 1 — Get the artifact to the reviewer

The reviewer runs in an isolated context and **cannot see this conversation**. That isolation is the point — it's what makes the review independent rather than a rubber stamp on reasoning you already agreed with. But it means anything the reviewer needs must be handed to it explicitly.

The artifact may live on disk or only in this conversation. Handle both:

| Situation | What to do |
|---|---|
| Already a file | Pass the absolute path. |
| Inline, and short (roughly under 400 lines) | Embed it verbatim in the dispatch prompt, inside a fenced block. No file needed. |
| Inline, and long | Write it verbatim to a temp file and pass the path. |
| Several files | Pass all the paths and say how they relate. |

**Verbatim is the non-negotiable part.** If you summarise or tidy the artifact on the way through, the reviewer critiques your summary and the findings won't map back onto anything the user can edit.

## Step 2 — Compose the reviewer's background

The right expert asks different questions than a generalist. A financial-services attorney reading a compliance memo goes looking for the regulator's angle; a systems architect reading the same memo doesn't know to look. Compose the persona fresh each time, in the dispatch prompt — there is no preset library, deliberately. A lookup table invites you to grab the nearest entry, and it also inverts the expertise: you would be a generalist telling opposing counsel what to look for. Your job is choosing *who*; how they think is theirs.

**Selection principle — adversarial alignment, not topic overlap.** Ask: *who is going to attack this in real life, and what do they know that the author doesn't?* That person is your reviewer. For a sales deck the marketer is topic-aligned but wrong — they'll critique the craft; the procurement lead who has to defend the purchase to their CFO is adversarially aligned and will find the number that doesn't hold up. For a defence brief, pick opposing counsel, not a legal generalist. For an architecture doc, often the on-call engineer who inherits it rather than the architect who'd admire it.

**Three parts. The third does the work.**

1. **Role and seniority** — "Principal engineer", "Senior litigator", "Regulatory examiner".
2. **Domain specificity** — the sub-field, not the field. "Distributed data systems", not "software".
3. **Scar tissue** — the specific experience that makes them dangerous. This is what shifts the review from textbook to earned; without it the persona reads like a job title and produces job-title findings.

Worked examples — note how distant these are from each other, and that each ends on the scar tissue:

> You are opposing counsel, twenty years in commercial litigation. You have watched confident causation arguments come apart under cross-examination, and you read every brief hunting for the one sentence that hands you the case.

> You are the procurement lead at the target account. You have to defend this spend to a CFO who has been burned before, and you have killed three vendors at this stage over numbers whose derivation they couldn't show.

> You are the engineer who will carry the pager for this system. You have inherited two builds on this exact pattern and been woken at 3am by both.

Don't hand the persona a list of angles to sweep — it is the domain expert and will generate sharper ones than you can. `references/reviewer-brief.md` gives it the universal angles; its own expertise supplies the rest.

## Step 3 — Assemble the context block

Most of what the reviewer needs is already in this conversation. Extract it rather than asking.

Pass a **bounded, factual** block: what the artifact is for, who will see it, what has already been decided and is off-limits, what's been tried and rejected, and what's at stake if it fails.

**Deliberately exclude your own view of the artifact** — praise you've given it, weaknesses you already suspect, your read of whether it's any good. The reviewer's independence is exactly what you're paying for, and seeding it with your framing quietly converts an independent review into confirmation of what you already thought. Facts about the situation, yes. Opinions about the work, no.

Ask the user directly only where a gap remains that would misdirect the whole review — typically the real adversary, or what's off-limits. Cap it at three questions in one batch. If you don't ask, state your assumptions in the dispatch prompt so the reviewer can flag any that are wrong, and so the user can correct a miss cheaply rather than discovering it buried in the findings.

## Step 4 — Dispatch the reviewer

Spawn **one** subagent with the `Agent` tool:

- `subagent_type: "general-purpose"` — deliberately **not** `"fork"`. A fork inherits your context, which means it inherits any sympathy you've built up for the artifact while helping write it. Independence is the product here.
- `model: "opus"` — the most capable model available, unless the user specified otherwise. Finding the non-obvious hole is exactly the task where model strength shows.
- `name` — something descriptive like `adversary-securities-law`, so you can follow up with `SendMessage` later. If the platform rejects `name`, you are yourself running inside a subagent (rosters are flat, so a subagent can't name-spawn another one) — retry without it and keep the agent id the tool returns instead. That id is your follow-up handle; capture it either way, because without a name it's the only one you get.

Compose the prompt from this shape:

```
<Persona: role and seniority, domain specificity, scar tissue — three parts, per Step 2.>

Review this artifact adversarially.

  Artifact: <absolute path(s), or the verbatim text in a fenced block>
  What it is: <one line>
  What it's for: <where it's going, what it has to achieve>
  Who will see it / who will attack it: <the real adversary, and what they want>
  Stakes: <what happens if it fails>
  Off-limits: <decisions already settled; constraints the remedies must respect>
  Already tried and rejected: <if any>
  Assumptions I made — correct them in your report if wrong: <...>

Read <SKILL_DIR>/references/reviewer-brief.md and follow it exactly. It defines your
method, your house style, your volume discipline, and both output formats.

Write your full report to: <output path — see Step 5>
Return the inline summary as your final message, in the exact format the brief
specifies. Nothing else — I have the file.
```

Substitute the real absolute path for `<SKILL_DIR>`. Having the reviewer read the brief itself, rather than you pasting it in, keeps your context lean and guarantees it gets the full instruction rather than your compression of it.

**Escalating to a panel.** Stay with one reviewer by default. Escalate to two or three when the artifact's failure would be expensive *and* it genuinely spans domains that no single expert covers — an architecture doc where security, cost, and operability are all live, say. Choose backgrounds that don't overlap, or you'll get the same findings three times in different vocabulary; give each an explicit lane and its own output file. Spawn them in the same turn so they run in parallel, then merge yourself: collapse duplicates, and where two reviewers disagree on severity, **keep the disagreement visible** — that split is information the user needs, not noise to average away. One merged plan, not three competing ones.

## Step 5 — Place the report and relay the summary

**The full report goes to disk. The summary goes inline.** The reviewer produces both — it has the reasoning that decided which finding is the first move, so re-deriving that yourself would be guesswork against its judgment.

**Output path.** Use this convention, which stands alone so the skill works in any workspace:

```
{YYYYMMDDHHmm}-review-{short-slug}.md
```

Written next to the artifact when the artifact is a file, otherwise in the working directory. If the workspace has its own outputs convention, follow that instead.

**Relay the reviewer's summary verbatim.** It arrives already in house style; rewriting it drifts the format and, worse, reintroduces your framing into an output whose whole value is that it isn't yours. Add the file path if the reviewer didn't. If the user asked for everything inline, paste the full report rather than summarising it a second time.

Two things to do rather than skip:

- **If the user disputes a finding, send it back to the reviewer** via `SendMessage` — it still holds the artifact and its reasoning in context. Re-litigating it yourself throws away the independence you just paid for.
- **If the user asks you to implement the remedies**, that's a separate act. Do it in a new turn against the artifact, and don't quietly expand past what the finding called for.

## What makes this fail

- **The scanner dump.** Thirty findings, no ranking. The user is now worse off than before they asked — they have a backlog instead of a next step. The brief caps findings for this reason; hold the line on it.
- **The invented Critical.** A reviewer that believes it must find something will manufacture one. A false Critical is worse than a missed Medium: it sends the author to rewrite a part that was fine, and it burns the reviewer's credibility for every later finding. "This holds up" after a genuine sweep is a valid, valuable result.
- **The substitution.** The reviewer proposes what it would have written instead. The artifact had value; a remedy that discards its approach is a rejection wearing a fix's clothing. Every remedy should leave the author recognising the work as theirs, improved.
- **Vibes as findings.** "This section feels weak" is not a finding. If there's no concrete probe that exposes it, it isn't ready to hand over.
- **Forking instead of dispatching fresh.** Convenient, and it silently destroys the independence that makes the whole exercise worth doing.
- **Seeding the reviewer with your opinion.** Same failure, quieter: the context block carries facts, not your verdict.

## Reference file

`references/reviewer-brief.md` — the reviewer's posture, method, house style, volume discipline, and both output templates. The subagent reads this itself; you don't need to. Read it only if you're tuning the skill or merging a panel's output.
