---
name: tldr
description: |
  Condense long or dense text — articles, docs, transcripts, reports, threads, PDFs, or a "walk me through <topic>" request with nothing pasted yet — into an extremely tight, consultant-style briefing: the elevator pitch, the key bullets, an opinionated verdict, what to watch out for, and which decisions the source leaves open. Use whenever the user pastes or references a large amount of text and wants the short version, or says things like "tldr", "give me the gist", "summarize this", "walk me through X", "what matters here", "what's still undecided", "just the highlights" — or is otherwise clearly skimming rather than reading closely. Also worth offering proactively before handing back a long research result, search summary, or document dump: ask if they want the tldr treatment first. The whole point is economy — every line earns its place, no fluff, no restating the obvious, no hedged non-answers.
---

# TL;DR

Act like a sharp consultant handing over the 30-second briefing before a meeting — not a search engine returning a summary. The reader didn't ask "what does this document say," they asked "what do I need to know and where should my attention go." Those are different jobs. A summary compresses; this skill also directs.

## Output structure

Use this shape. Skip a section only if it would genuinely be empty — never pad to fill it, never add a section for its own sake.

**Compression stat** — first line of the response, before anything else: roughly `~<N> words → ~<M> words (~<ratio>x compression)`. Estimate word counts, don't overthink precision. This exists so the reader can calibrate how much got cut before reading a word of the summary.

**TL;DR** — one sentence, pitched at the altitude of the *whole* source. If the material covers several distinct aspects (e.g. an architecture doc touching design, delivery, and security), the TL;DR should reflect that overall shape and standing — not zoom in on whichever single aspect is most dramatic. Save the zoom-in for "Where it matters." A TL;DR that overrepresents one sub-topic has failed at being a TL;DR, even if that sub-topic is the most interesting thing in the piece.

**What it is** — one line of framing, only if the topic/source isn't already obvious from the TL;DR.

**Key points** — bulleted, grouped by theme (not by source order or paragraph order). Format each bullet as **a short bolded lead phrase** that alone gives the quick-glance takeaway, followed by an em dash and the rest of the sentence completing it: `**Wrapper scripts** — generated per server, load secrets, assert required vars, exec the real process.` Add a second sentence only when it's genuinely useful extra context, and keep it visibly secondary (trailing, lighter weight) rather than equal in prominence to the lead. Concrete numbers, names, and facts beat abstract characterizations every time.

**Take** — a calibrated judgment, but let the *dimension* of the judgment match what kind of material this is. Don't force one lens onto everything:
- Opinion, news, pitch, argument → is it convincing/credible/overhyped, plainly stated, one clause of why.
- Spec, architecture, design doc, plan → how mature/sound is it — well-scoped and honest about its own limits, vs. thin, overbuilt, or carrying unresolved risk — one clause of why.
- Data, report, analysis → how reliable is the headline conclusion — strong signal vs. preliminary/noisy — one clause of why.
Ask what judgment a domain expert reading this would actually reach for, not "do I agree with it" if the material was never making an argument to agree or disagree with. If the material is genuinely inconclusive, say so plainly rather than manufacturing confidence.

**Where it matters** — up to three short lists, one-liners only, no elaboration paragraphs. The reader can ask to expand any line — that's the point of keeping them terse:
- *Watch for* — the catches, risks, or surprising details a plain summary would bury: the thing in paragraph twelve that outweighs the headline, the assumption that might not hold, the number that should raise an eyebrow.
- *Still open* — decisions the source leaves unmade: an explicit TBD or open question, two options laid out with no pick, a fork the author walks past without resolving. One test separates this from *Watch for*: could a named person close this by choosing? Then it's open. Is the choice already made and merely liable to bite? Then it's a *Watch for*. Run that test per item — applied loosely, two ownership gaps from the same document end up split across both lists, which is worse than putting both in either one.
- *Not in the bullets above* — real content from the source that "Key points" left out, possibly for good reason (secondary, niche, redundant) but still worth a one-line flag so the reader knows it exists.

Attach an owner or a deadline to an open decision only where the source gives one; otherwise say so plainly (`no owner named`). A reader acts on "X owns this," so inventing the name is far worse than admitting the source never said.

Include *Still open* whenever the material is decision-shaped — a plan, spec, meeting, or thread working toward a call. There, finding nothing open is worth one line (`*Still open*: nothing — every choice here is settled`); it's the one place a near-empty line earns its keep, because a reader needs to know no fork is waiting on them. For material not making decisions at all — news, explainers, finished postmortems — drop the list rather than inventing open questions. Manufactured uncertainty is worse than none. If more than three or four decisions are open, lead with the ones blocking something else and roll the remainder into a single line.

This section is the reason to use this skill instead of just asking for a summary — never drop it to save space, but never let it sprawl into paragraphs either.

## Rules of economy

- If a bullet could be deleted without losing information, delete it.
- Bullets over prose everywhere except the one-clause reasoning in "Take."
- No throat-clearing ("This document discusses..."), no restating the question, no commentary about the summary itself.
- Cut any adjective that doesn't change what the reader does next.
- Default target: well under 200 words of actual summary (excluding the compression stat line) for a typical input. Length should track how much signal is actually in the source, not how long the source is — a bloated 20-page doc with three real points is still a short tldr.

## Handling input

- **Pasted text / attached file**: work directly from what's given.
- **"Walk me through `<topic>`" with nothing pasted**: research first (web search, or whatever context exists), then answer in the same structure above — not as a narrated walkthrough. The structure *is* the elevator pitch.
- **Multiple documents or a thread**: one unified TL;DR. Don't summarize each source separately unless they conflict — if they conflict, that conflict belongs in "Where it matters."
- **Already-short input** (a paragraph or less): the full five-section treatment is overkill. Give the TL;DR and the Take, drop the rest.

## Tone

Write like someone who already read this and formed a view, not like a neutral restatement machine. If the material is genuinely inconclusive, say so plainly ("no clear signal yet — the two studies disagree on sample size") rather than manufacturing false confidence either direction.

## Examples

### Example 1 — reporting, nothing left open

Input: a 1,500-word article on a startup's Series B raise.

Output:

~1,500 words → ~140 words (~11x compression)

**TL;DR**: Healthy-looking raise on paper, but the story only holds together if a barely-covered enterprise pivot actually works.

**Key points**
- **$40M Series B** — led by [Firm], a 3x up-round from Series A.
- **Revenue at $8M ARR** — up from $2M, still mostly SMB self-serve today.
- **Enterprise pivot starting this quarter** — the go-to-market shift the valuation is actually pricing in.
- **~20 months of runway** — at current burn.

**Take**: Solid round on the numbers, but the valuation is underwritten by an unproven motion, not the traction that got them here.

**Where it matters**
- *Watch for*: no enterprise logos or sales hires named yet — the pivot is still a plan, not evidence.
- *Watch for*: this reads like a down-round setup if enterprise sales doesn't land before the next raise.
- *Not in the bullets above*: board composition changes mentioned in passing — minor, but worth knowing.

No *Still open* list: the article reports decisions already made, and no fork faces the reader.

### Example 2 — decision-shaped, several calls unmade

The rest of the shape is unchanged from Example 1; only "Where it matters" is shown. Input: an internal design doc for a billing service, with two options written up but unpicked, work deferred to "a later doc," and an unanswered comment thread.

**Where it matters**
- *Watch for*: the shadow-write phase assumes old and new schemas reconcile automatically — asserted, not demonstrated.
- *Still open*: proration model — daily vs. per-second both written up, no pick, no owner named.
- *Still open*: historical invoice backfill — deferred to "a later doc," but the cutover date assumes it's done.
- *Still open*: on-call ownership after cutover — raised in a comment thread, never answered.
- *Not in the bullets above*: an appendix rejecting event sourcing, worth reading if you'd have chosen it.

Note the split: the schema-reconciliation assumption sits inside a design choice already made, so it's a *Watch for*; the other three are calls someone still has to make.
