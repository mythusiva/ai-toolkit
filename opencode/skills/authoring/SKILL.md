---
name: authoring
description: Write anything a human reads or watches - technical articles, investigation write-ups, current-state and design docs, review findings, runbooks, wiki pages, PR descriptions, chat posts, decks, pitches and narrated video scripts. Use whenever the deliverable is prose, tables, slides or spoken copy rather than code - "write this up", "document how X works", "turn this into a doc", "make a deck", "write the pitch", "script the video". Owns the reading budget, layout, structure and language.
---

# Authoring

One set of rules, two shapes. **Part 0 holds for both.** Then read Part 1 or Part 2, not both.

| The deliverable is… | Read |
|---|---|
| Something read at the reader's pace: doc, article, findings, runbook, PR description, post | Part 0 + **Part 1** |
| Something watched at *your* pace: deck, pitch, video | Part 0 + **Part 2** |

---

# Part 0: holds for everything

## 1. Budget: 3 minutes, counted

Every document fits **180 seconds of reading**. Count it, don't eyeball it.

| Element | Cost |
|---|---|
| Prose, technical | words ÷ 200 wpm |
| Prose, business | words ÷ 250 wpm |
| Diagram | 30 s |
| Table | 20 s |
| Code / config block | 15 s |
| Screenshot | 10 s |

Worked example: 2 diagrams + 1 table = 80 s, leaving 100 s ≈ 330 words of technical prose.

- **Diagrams are the lever.** A diagram costs 30 s and replaces ~200 words (60 s) of prose saying
  the same thing. Any mechanism, flow, sequence, state machine or before/after is a diagram.
- **Over budget → cut.** Never shrink prose by deleting the diagram; the diagram bought the time.
- **Never print the estimate** in the document. Report it in chat if at all.
- **First 100 words: the answer and what it costs.** Readers grant ~25 s unconditionally and ~4.4 s
  per extra 100 words (NN/g, *How Little Do Users Read?*); the median reader stops halfway
  (Chartbeat, 2013).

## 2. Open plain

Every PR description, post and article opens with a paragraph a five-year-old could follow: plain
words, one everyday analogy, no jargon, no file paths. A reader who stops there still knows what
broke, who it hurt and what changed. **Never label it** ("ELI5:", "In plain words:"); the paragraph
simply opens the text. Technical detail comes after.

## 3. Audience is fixed, not guessed

- **Technical → a junior dev.** Define every term at first use in one clause, expand each acronym
  once, name the trap. Assume zero context on the system's internals.
- **Business → a product manager.** Lead with impact, cost, risk, timeline. No file paths or table
  names: replace each technical noun with its consequence.

## 4. One repeated micro-schema

Pick fixed labels for a repeating item and use exactly those, in that order, every time. The
reader learns the shape once and skims by label.

```
<one paragraph: the mechanism, as a causal chain>
**Impact:**    <what the user or the business loses>
**Affected:**  <services / screens>
**Current:** / **Recommended:** / **File:** `path` lines N–M
```

A schema applied to four of six items is worse than none.

## 5. Tables carry decisions. Prose carries only mechanism.

"Which one, and why" is a table: **thing | verdict | why**, verdict bolded, under four words.

| Change | Flag it? | Why |
|---|---|---|
| Money movement, ledger entries | **Always** | Even an obviously correct fix needs gradual rollout |
| New API field, zero callers | **No, inert** | No effect until a client calls it |
| Admin tool writing to prod data | **Judgment** | Flag if it writes; skip if read-only |

Never restate a table in prose. Prose has one job: the causal chain, in the order it happens.

> If the payment provider goes slow, the caller holds connections open until it runs out of
> threads and goes down too.

## 6. Every claim carries its number, source and location

`config.tf` lines 43–45 · `+$52/mo` · `250 rps` · `maxSize = 20` · `n=943k`. No "significant",
"several", "may be large". Unmeasured → prefix `unverified:`. **A claim the implementation does
not back gets cut, not softened.**

## 7. One emphasis per unit

One callout per section (or one highlighted element per slide): the single line that, if missed,
makes the reader do the wrong thing.

## 8. Simple language, without overexplaining

**Explain what is specific to this system. Assume what is general.** A junior dev knows what an
index, a queue and a cache are; they don't know that *this* `User` entity eagerly loads two
relations on every query.

| Rule | Do | Don't |
|---|---|---|
| Define once, in one clause | "a feature flag (a switch that turns a feature on for some users)" | A Terminology section |
| Shortest common word | uses · so · before · about · start | leverages · thereby · prior to · initiate |
| One idea per sentence | Two sentences | One joined by "and which" |
| Second person, imperative | "Skip it for standard releases." | "It may be skipped in…" |
| Name the trap | "Existing topics need manual repartitioning." | Leaving the gotcha to be hit |

**Delete test:** delete the sentence. If a junior dev still gets it right, it stays deleted. Apply
it to everything starting "This means", "In other words", "Essentially". Never write a line that
only restates its heading.

## 9. Say what you are *not* doing

A real **Non-goals** list, or a **Problem today | What it costs** table before you propose anything.

## 10. Finish with the thing they use tomorrow

Never a summary. A `- [ ]` checklist, phased rollout, or numbered runbook. Phases key on risk:

```
Phase 1 — Zero downtime, do today
Phase 2 — Maintenance window (~5 min failover)
Phase 3 — Recreate the cluster, off-peak
```

---

# Part 1: documents

## 1.1 Page shape

Top to bottom, in this order. Skip a row that doesn't apply; never reorder.

| Element | What it is | When |
|---|---|---|
| Plain opener | Part 0 §2 | Always |
| Scope line | One sentence: what this doc is, and what it replaces | Always |
| Thesis callout | 2–3 sentences a reader could quote back | Any doc making a case |
| Body | Sections, tables, diagrams | Always |
| The usable thing | Checklist, phases, or runbook | If the reader must *do* something |

No Introduction or Background section: the scope line is the introduction. No appendix and no
collapsed sections: what doesn't fit the budget gets cut or moves to a separate linked doc.

## 1.2 Findings and triage lists

ONE numbered table (number, location, one-line claim, severity). The reader replies with the
numbers to act on. Per-finding detail is on request, not up front.

## 1.3 Emoji are an index, not decoration

At most one per `##` heading, and a fixed scale for any ranking. Never mid-sentence.

🔴 P1 · 🟠 P2 · 🟡 P3 · 🔵 P4 · ⚪ P5

---

# Part 2: presentations, pitches and video

**The audience rule inverts.** Spoken copy argues to the market: lead with the customer's situation
and the behaviour shift, give the tech exactly **one** benefit sentence, and put the architecture
on an appendix slide or save it for questions.

## 2.1 Spoken copy is beats, not paragraphs

1. One idea per line. Line breaks are breath marks.
2. Fragments are whole beats. "Picture this." / "Done."
3. Say **why now**: name the behaviour change and the competitors out loud.
4. A thesis, repeated as a refrain mid-way and again as the closer.
5. Close on positioning plus the product name, never on a demo flex.
6. Numerals, not spelled-out numbers.

## 2.2 Length is set by word count

Narration runs ~2.3 words/second. Write `target_seconds × 2.3` words.

| Target | Words |
|---|---|
| One slide (~25 s) | ~57 |
| 30 s | ~70 |
| 60 s | ~140 |

Hold the whole thing to **≤2 minutes**: completion is 66% under 1 min, 56% at 1–2 min, 50% at
2–10 min (Vidyard).

## 2.3 What the evidence supports

| Rule | Evidence |
|---|---|
| Open on the payoff, never a title card | Vidyard n=943k B2B videos: engagement peaks in the first quarter |
| Land the strongest proof inside ~30 s | Wistia n=13M: drop-off clusters at the halfway mark |
| No static shot past ~10 s | eye-square eye-tracking: 62.5% stop looking after 2.5 s |
| Burn in captions | Verizon/Publicis n=5,616: 69% watch muted in public |

Reject uncited folklore ("cut every 2–4 seconds").

## 2.4 Visual grammar

One 16:9 diagram that builds beat by beat, never a slideshow of text posters. The element being
narrated is at full contrast; everything already established recedes (~34% opacity). For a
proposal, transform today's diagram in place rather than drawing a new one.

## 2.5 Two traps that ship broken

- Narration and on-screen text are separate sources: after every wording fix, grep the slides for
  the old phrasing.
- Text-to-speech misreads digits (`401` → "four hundred and one"): respell them in the script.

---

## Before you publish

- [ ] Plain opener, unlabelled; first 100 words / 6 seconds state the answer
- [ ] Counted against 180 s (diagrams 30 s, tables 20 s, code 15 s); estimate not printed
- [ ] Repeating items use the same labels in the same order
- [ ] No table or slide restated in prose
- [ ] Every number has a source; unmeasured → `unverified:`; unbacked claims cut
- [ ] Every term defined once at first use; nothing survives the delete test
- [ ] Non-goals written down
- [ ] Ends with a checklist, phases or runbook, not a summary
- [ ] Spoken copy: one-idea lines, why-now beat, refrain, `seconds × 2.3` words, ≤2 min
