---
name: plan-and-critique
description: Use this skill for any non-trivial creative or design task where the user wants a thoughtful plan or artifact rather than an immediate output — designing systems, drafting architectures, scoping projects, planning research, structuring complex documents, building skills or subagents. The skill enforces a disciplined cycle of brainstorm → elicit → draft → adversarial self-critique → revise, with explicit stopping criteria. Use this skill proactively whenever the request is open-ended ("help me design X", "I want to build Y", "plan out Z") and the cost of getting it wrong is meaningful enough to justify a critique pass before delivery. Do not use for narrow lookups, code fixes, conversation, or tasks where the user has already specified the deliverable in detail.
---

# Plan and Critique

Disciplined iteration for non-trivial creative work. The default model behavior is to draft immediately and treat self-review as light polishing; this skill imposes a brainstorm-first, elicit-the-questions-that-matter, draft-in-earnest, critique-adversarially, revise-honestly cycle. The loop itself isn't novel — every senior practitioner knows it. The point is that it doesn't run by default. This skill makes the discipline the default.

## When this skill applies

- The user wants a plan, design, or artifact — not just an answer.
- The task is open-ended enough that there are multiple reasonable approaches.
- Getting it wrong has a meaningful cost: wasted work, brittle output, a path that won't generalize.

## When NOT to use this skill

- Narrow lookups, single-step code fixes, factual questions.
- The user has already specified the deliverable in detail and wants execution, not planning.
- The user has explicitly asked for fast iteration without ceremony ("just give me a draft", "no need to overthink"). Respect this — the skill imposes friction by design, and the user gets to decide when friction earns its place.
- Conversation, emotional support, anything where the social register is informal.

## The loop

```
1. Brainstorm  → expand the option space before narrowing it
2. Elicit      → ask only the questions whose answers would change the output
3. Draft       → produce the artifact in earnest, no placeholders
4. Critique    → run structured adversarial review
5. Revise      → address what survives the critique
6. Stop        → when stopping rules say stop
```

Each step has discipline. The discipline is what makes the loop work; without it, this collapses into "draft and lightly polish."

## Step 1: Brainstorm

Before locking onto a single approach, briefly expand the space of approaches. The point is to _not_ commit prematurely to the first framing that came to mind.

This step is short — usually three to five sentences. It is not an essay; it is a deliberate widening before narrowing.

**What to do in this step:**

- Generate two or three meaningfully different framings of the problem. Not three flavors of the same approach — three approaches that would lead to different artifacts.
- For each framing, name what it optimizes for and what it sacrifices.
- Pick the framing you'll pursue, with one sentence on why.

**Skip this step if:**

- The user has already specified the framing in the request and there's no genuine ambiguity.
- The task is sufficiently constrained that meaningful alternative framings don't exist.

**Don't skip this step if:**

- The request is open-ended ("help me design X", "I want to build Y").
- You notice yourself reaching for the first framing that came to mind without considering whether it's the right one.

**Failure mode this prevents:** anchoring on the first plausible approach and producing a competent execution of the wrong plan.

## Step 2: Elicit

Ask only the questions whose answers would change the output. Skip questions you can answer yourself by reading context.

**Hard rule: ask before drafting if you'd otherwise have to invent any of these:**

- The user's actual goal — not the surface request, the underlying outcome they want.
- Constraints that would invalidate certain approaches (deadline, environment, prior decisions, team size, audience).
- The intended consumer of the output and what they need from it.
- What "good enough" looks like — what level of rigor or completeness matches the situation.
- What's already been decided that should not be revisited.

**Skip if you can infer:** anything where context already gives a clear answer. Don't perform clarification theatre.

**Limit:** three questions maximum, in one batch. More than that means you haven't done your own thinking. If you genuinely need more, ask the highest-leverage three, draft against best-effort assumptions for the rest, and surface those assumptions for the user to correct in the critique phase.

**The brainstorm interaction:** if the brainstorm produced multiple plausible framings and you can't pick between them from context, surface them as a question rather than picking arbitrarily. "I see two ways to read this: [A] or [B] — which is closer?" is a high-leverage question; it counts toward the three-question budget.

## Step 3: Draft

Produce the actual artifact — plan, design, document, structure. No placeholders, no "[TODO: fill in here]" — drafting in earnest is what gives the critique something real to attack.

**State assumptions explicitly inline.** If you assumed something about scale, environment, or context that the user didn't specify, say so where it matters. The critique phase will check assumptions; it can't check what wasn't surfaced.

**Length discipline:** aim for the shortest draft that's actually a complete artifact. A plan that's missing parts isn't a draft, it's an outline — those don't critique well.

**The provisional-confidence principle:** for design choices made from limited evidence, label them as provisional rather than authoritative. "I'd suggest X for this case, though if you build a few of these you'll see whether it generalizes" is more honest than "X is the right pattern."

## Step 4: Critique — the part that earns its keep

This is where most "iterative refinement" workflows fall apart. A vague "review your draft" produces toothless self-praise. The critique must be **structured** and **adversarial** — actively looking for problems, not pattern-matching to "looks fine."

Run the draft against the angles below. For each, be specific about what you find.

### Standard critique angles

**1. Premature generalization.** Are you encoding patterns from a small sample as if they were universal? Flag every "always" or "never" that wasn't earned from multiple instances.

**2. Hidden assumptions.** What are you assuming about the user, environment, scale, or context that you haven't stated? Surface them. The user will catch them otherwise, later, with more cost.

**3. The strongest objection.** If a competent skeptic read this draft, what's the single strongest criticism they'd raise? Address it head-on, in the artifact, not by hand-waving.

**4. The trivial-or-wrong test.** A common failure mode is content that's either obvious to the reader (waste of their time) or confidently incorrect (worse). For each major claim, ask: would the reader's reaction be "yes, obviously" or "wait, is that right?" Both responses indicate a problem.

**5. Coverage vs. depth.** Did you produce a thorough-looking artifact that touches everything but commits to nothing? Or a depth-focused artifact that leaves real gaps? Both are real failure modes; identify which way this draft leans.

**6. The "in six months" test.** If you came back to this artifact in six months — or someone else inherited it — would the design choices still make sense? Would the rationale be obvious from the artifact? Are you encoding decisions that depend on context that won't be available later?

**7. Stop conditions.** Did you specify when the artifact is "done" or when its prescriptions stop applying? Open-ended plans without stopping criteria become zombie documents.

**8. Path-not-taken honesty.** From the brainstorm step, you considered alternative framings. Does the draft acknowledge what was rejected and why? If a reader would reasonably wonder "did you consider X?", the answer should be in the artifact, not lost.

### Optional critique angles (use when relevant)

- **Token / context efficiency** (for skills, prompts, agent designs): is the draft paying recurring cost on every load? Could it be smaller without losing teeth?
- **Failure modes** (for systems and pipelines): what specifically breaks first, and what happens then? Is recovery possible?
- **Compatibility** (for tooling and integrations): what changes upstream would break this?
- **Provisional vs. authoritative honesty** (for anything abstracted from few examples): are you presenting "this worked once" as "this is the right pattern"?

### How to write the critique

Critique is a list, not prose. For each angle that finds something:

```
[Angle name] → [specific issue, one or two sentences]
```

Then: _which of these are worth addressing now?_ Not all critiques warrant a revision. Some are notes for later, some are by-design tradeoffs, some are out of scope. Triage explicitly.

If the critique finds nothing worth addressing, say so — but only after running every angle. "No issues found" without going through the angles is the failure mode this skill is designed to prevent.

## Step 5: Revise

Address what the critique flagged as worth addressing. Don't address everything — that's how loops fail to terminate.

For each addressed item, the revision should be visible in the artifact, not just in commentary. Don't "note that X is a concern" — fix X.

Track what you didn't address and why, briefly, in a delivery note alongside the artifact.

## Step 6: Stopping rules

Stop iterating when **any** is true:

- Two consecutive critique passes find nothing worth addressing.
- Remaining critiques are out of scope or by-design tradeoffs the user already accepted.
- The user has signaled they want delivery — explicitly or by drift in their messages ("okay, looks good", "let's go with that", or just lack of further engagement on substance).
- You've completed three full revision cycles. Beyond three, you're refactoring, not refining.

The failure mode this prevents: the perfectionist loop that never ships. Iterative critique without stopping rules is worse than no critique at all — it eats time and produces over-elaborate artifacts.

## Output structure

When the loop converges, deliver:

1. **The artifact itself** — clean, no critique annotations.
2. **A short delivery note** — what was iterated on, what was deliberately not addressed, what's still open. Three to six bullets, not an essay.
3. **(Optional) Critique log** — if the user asked for the reasoning, or if the critique caught something that materially affects how they should use the artifact.

## Anti-patterns

- ❌ Skipping the brainstorm step on open-ended requests. Anchoring on the first framing is the most common failure.
- ❌ Skipping the elicit step "to be helpful." If the questions would change the answer, asking them _is_ the helpful move.
- ❌ Asking more than three questions up front. That's offloading thinking to the user.
- ❌ Vague critique ("looks good", "could be tighter"). Specific or skip it.
- ❌ Addressing every critique. Triage is part of the discipline.
- ❌ Iterating past the stopping rules to seem thorough.
- ❌ Critiquing a draft in a way that praises it. The critique angles are adversarial by design.
- ❌ Hiding provisional choices behind authoritative language. If you're not sure, say so.

## When to use this skill alongside others

This skill is the loop, not the content. For domain-specific work it pairs with:

- A domain skill that supplies the methodology and content.
- A checklist or template if one exists for the artifact type.

Load this skill when the task is "produce a non-trivial design or plan" regardless of domain. The critique angles above apply broadly; domain-specific critique angles (if any) come from the domain skill or checklist.
