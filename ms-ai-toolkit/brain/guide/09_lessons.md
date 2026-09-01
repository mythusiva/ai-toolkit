Hard-won failure modes of THIS system, from 31 monitoring passes that found 27 defects.
Every single one was SILENT. Read this before you change any part of the machinery.

ON SIGNALS
- A signal is only as good as its chance of being READ. The stale view flagged 31 sha-verified
  rows and taught its reader to ignore it; the key warning printed before the success line and was
  ignored by its own author twice. Neither was a discipline problem.
- Never age-flag something already verified by a stronger signal.
- Put the warning AFTER the success line. The last thing on screen should be the problem.

ON MEASUREMENT
- Measure the thing you care about. Every automatic number was improving while PRECISION - the
  only one that matters - was 30%, and it had never been measured.
- Relevance cannot be measured automatically. A token-strength proxy read 18% where hand judgement
  read 50%. It was deleted. Sample the delivery log and judge by eye.
- A parser that silently returns nothing is indistinguishable from a system doing nothing. Both
  render as a clean report. Make parsers prove they can parse a known-good sample first.
- An automated observer that emits the same kind of event it measures will dominate its own data.
  Filter by provenance, and filter BOTH sides of every ratio.
- Verify the verifier before correcting the record. Grepping `status *= *` matches `===`, and
  nearly produced a false correction to a correct fact.

ON SILENT SUCCESS
- Success is the default output; every component must be FORCED to admit failure. Three commands
  reported success doing NOTHING, one reported success while DELETING work, and the audit exited 0
  while reporting total catastrophe. All printed the same cheerful line. Concretely: an UPDATE
  that matches no rows must be an error, not a success -- check rowcount every time.
- Sweeping a defect CLASS beats fixing instances. One structured pass over every mutating
  statement found the last case and PROVED the INSERTs were never at risk.

ON SEAMS
- Components correct against their own spec are still wrong together. A recall injection faked a
  write and silenced the capture nudge; a key validator checked shape while the read path could
  not retrieve the key. Probe seams by running a value ALL THE WAY THROUGH.

ON RULES
- When you break your own written rule three times, the rule FORMAT is wrong, not your discipline.
  Move it into something that fires on its own trigger.
- A green suite proves only what it tests. After fixing anything, add the case that would have
  caught it IN THE SAME TURN.
- A doc that must be hand-synchronised with a live system is wrong by default, and more
  confidently wrong than one that points at the system.

THE ASYMMETRY WORTH REMEMBERING
- 27 defects in the machinery; ZERO in the content. Every fact hand-verified (9 of 9) held up,
  several to the exact line number. Knowledge written with its evidence at the moment it was
  proven survives; the tooling around it does not, unless continuously poked.

ON WHAT IMPRECISION ACTUALLY COSTS
- A relevant injection changes behaviour: agents opened with 'Checking the brain first, then the
  code' and queried before touching code.
- An IRRELEVANT injection is ignored, not acted on. A PR-review session that received unrelated
  gotchas went straight to the PR anyway.
- So precision is an EFFICIENCY problem (wasted tokens), not a correctness one. Correctness risk
  lives in the content being WRONG - and 9 of 9 hand-verified facts held up. Spend effort
  accordingly: guard content accuracy hard, treat precision as cost control.

ON WHAT ACTUALLY DRIVES CAPTURE
- The evidence-triggered end-of-turn nudge converted 4 of 4 INDEPENDENT sessions into writes. One
  replied: 'Fair - that orientation cost real calls. Writing the map rows and the two ceremonies
  I had to rediscover.'
- The agent-brain SKILL was invoked ZERO times across the same period. The skill is not what
  drives capture; the hook is. Put process guidance where the process happens, and make the
  trigger fire on evidence rather than on the model remembering to look.

ON SKILLS VERSUS HOOKS
- A skill competing with a hook for the same trigger always loses. The hook fires on EVIDENCE; the
  skill fires on the model remembering to look. Point skills at the judgement calls a hook cannot
  make, and say so in the skill's own description.

ON BASELINES
- A baseline without its variance invites chasing noise. Small-sample metrics (capture rate over
  6 sessions, precision over 10 hand-judged rows) swing 10-20 points on one session; one moved
  40 -> 33.3 within an hour with nothing changed. Mark volatile metrics as volatile, or the next
  reader 'fixes' the noise.

ON DURABILITY
- Anything scheduled from inside a session dies with that session, and nothing reports the death.
  Durable monitoring has to live in a session-start hook, because every new session re-arms it
  for free.
- Keep that hook CHEAP and SILENT: ~50ms, speaks only on a problem, and points at the expensive
  check rather than trying to diagnose. The full check is ~11s and would be intolerable per-session.
- A daily snapshot wired only to session start has a hole every day nobody starts a session, and
  a trend read off the table treats that hole as data.

ON DUPLICATED DEFINITIONS
- Two components that must agree WILL diverge if each restates the rule. A capture-rate metric
  disagreed with the capture nudge on both what counts as learning and what counts as a write,
  and each divergence pushed the number down independently. The fix is not to re-sync them but to
  make one READ the other. Verify the coupling by changing the source of truth and watching the
  dependent move.

## When a metric is flat, check whether the mechanism can even fire
code_map sat flat for three days and the proposed fix was to sharpen the wording in the skill.
That lever was REJECTED on evidence: over the same days fact +20, gotcha +12, recipe +2,
decision +4 -- so sessions WERE writing, and the nudge already named map first. Guidance was
never the binding constraint. The real cause was one boolean in the capture hook: `wrote` was a
single flag, so any one write silenced the nudge for the whole session, including sessions that
had spent dozens of calls locating symbols and owed a map row. Fix: track wrote_map separately
and still block once, with a narrowed map-only message.
Generalises: rewriting prose guidance is the lever people reach for first and it is usually the
wrong one. The suite that guards this is brain-selftest.py, and it was written only after the
bug -- the capture hook had NO tests before, which is exactly why the bug was silent.

## Two silent recall defects, both found by the retrievability RATIO climbing
Trigger: a session added 10 rows and unreachable went 5/311 -> 8/321, i.e. 3 of 10 NEW rows were
unfindable (30%) against a 1.6% baseline. The ratio, not the absolute count, is the signal.
1. STOPLIST OVER-REACH. local, hook, table, prod, repo, query, master, column were stopped as
   generic English. In a technical corpus they are domain nouns and carry signal. Freeing them
   fixed it. NOTE `start` was freed too and had to be put back: it is a common verb and broke a
   must-stay-silent case. Free concrete technical nouns, never common verbs. Your ORG NAME is the
   opposite case -- every path on the machine contains it, so it belongs in BRAIN_STOP_EXTRA.
2. PER-TERM TRUNCATION BEAT MULTI-TERM RANKING. The fetch was LIMIT 8 PER TERM, applied BEFORE
   scoring by term count. A row matching two moderately common terms fell out of both top-8 lists,
   so the ranker never saw it. A cap below the broad-term threshold silently discards rows the
   broad filter has already accepted; those two numbers must never be set independently.
Result: unreachable 8/321 -> 4/327, must-hit 29/29, must-silence 7/7, 45ms.
Rejected: asserting a specific row ranks FIRST. A sibling row matching the same terms wins the
rarity tie-break, which is correct behaviour; reachability was the defect, not ranking.

## Write the key in the words the next agent will type
Recall matches ordinary words against a row's KEY, not its body. A key that describes the problem
abstractly is unfindable. Measured: the key `UPDATE t SET col=expr1, col=expr2 in one statement`
returned nothing for the prompt "sqlite update with two replace calls on the same column";
rewording it to `sqlite UPDATE setting the same column twice (col=replace(...), col=replace(...))`
made it match.
- A kebab-case key is the most retrievable shape there is. A space-free key is treated as an
  identifier and matched per segment, so EVERY word in it becomes a search term.
- Put the tool or vendor name in the key. Put the word you would have SEARCHED for in the key,
  not only the precise technical phrasing.
- Keep prose keys short. A key longer than 5 words needs two distinct query terms to match.
- Words buried in a path or identifier inside a PROSE key are invisible: a plain word must be
  delimited by whitespace. That is deliberate -- it is what stops your org name inside
  `org-repo/scripts/...` firing on unrelated prompts. Kebab the whole key instead.
- Avoid colloquialisms. "...the Next button just looks dead" matched "thanks, that looks good".
- Never key a row on a file path alone.

## The key guard only fires through the helper; raw SQL bypasses it
brain-note.py checks every key it writes and warns when the read path will not be able to
retrieve it. A hand-written `UPDATE ... SET subject=...` consults nothing, and that is how a
62-character kebab key got written during this package's own build -- two characters over the
limit at which per-segment matching silently switches off, which is the entire reason a kebab key
is retrievable in the first place. The row was findable by its exact key (so brain-retrieve.py
called it healthy) and unfindable by the sentence anyone would actually type.
Rule: rekey through `brain-note.py`, or run `check_key` on the new key before committing the SQL.
Generalises: a validator reachable only from the convenient path will be bypassed on the
inconvenient one, and the bypass looks like success.

## Brain-internal lessons go HERE, not in a gotcha row
fact and gotcha rows with scope='agent-brain' are EXCLUDED from the search view on purpose, so
they are unreachable by recall. If you learn something about this system, append it to this
topic's FILE (@SCRIPTS@/guide/09_lessons.md) and re-run brain-init.py --guide.
