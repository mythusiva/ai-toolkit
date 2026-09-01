---
name: agent-brain
description: Work ON the agent brain rather than just writing to it: retire a fact that turned out wrong, work out why recall is not finding something, claim or release work so parallel agents do not collide, restructure the schema, or check the brain is healthy. Use when a stored claim is contradicted by what you just saw, when a search should have hit and did not, when you are about to touch a branch another agent may hold, or when the user asks how the brain works. NOTE routine capture does NOT need this skill - an end-of-turn hook already prompts for it with the exact commands, and converted 4 of 4 independent sessions; this skill is for the judgement calls the hook cannot make.
allowed-tools: Bash, Read
---

Work **on** the brain. Routine capture does not need this file: the capture hook fires on
evidence of learning and hands over the exact `brain-note.py` commands, and it converted 4 of 4
independent sessions. A skill competing with a hook for the same trigger always loses — the hook
fires on evidence, the skill fires on you remembering to look. This skill was invoked ZERO times
in the period its hook converted 4 of 4, because its description used to target the moment the
hook already owns.

What the hook cannot do, and this file is for:

| Judgement call | Section |
|---|---|
| Retiring a wrong fact — supersede it, never delete it | §2 |
| Diagnosing why recall missed something that is in there | §3 |
| Claiming work so parallel agents do not collide | §4 |
| Restructuring the schema, which is explicitly sanctioned | §6 |
| Checking the brain is healthy after any of the above | §5 |

```sh
DB="${BRAIN_DB:-$HOME/.agent-brain/brain.db}"
BRAIN="${CLAUDE_PLUGIN_ROOT:-$HOME/.agent-brain}/brain"    # where the scripts live
```

Other agents hold the same file, so always write with a timeout:
`sqlite3 -cmd ".timeout 5000" "$DB" "<sql>"`

## 1. Decide whether there is anything to write

Write a row when **the next agent would waste tool calls without it**. That is the only test.

| Did this happen? | Table |
|---|---|
| I proved something about how the system behaves | `fact` — **evidence is mandatory** |
| I had to hunt for where a symbol or behaviour lives | `code_map` |
| Something surprised me and cost more than ~2 tool calls | `gotcha` |
| A command only worked after fiddling with env/cwd/flags | `recipe` |
| A fork got settled, by the user or by evidence | `decision` — **record what was rejected** |
| The user corrected an assumption I made | `fact` (`disproven` on the old one) + `gotcha` |
| I decided NOT to act on an inbound item | `thread`, `state='declined'` + `verdict` |

Do not write: anything already in the DB (the recall hook may have already shown it to you),
anything the repo itself makes obvious, or anything true only for this conversation.

## 2. Supersede, never delete

```sh
sqlite3 "$DB" "SELECT kind,key,substr(body,1,120) FROM search WHERE key LIKE '%TERM%' OR body LIKE '%TERM%';"
```

Already there and still right → `brain-note.py bump <table> <id>`, do not insert a duplicate.

Already there and now wrong → **do not delete it.** The disproof is what stops the next agent
re-deriving the dead end, and a `disproven` row stays visible in `search` with a shouted prefix:

```sh
python3 "$BRAIN/brain-note.py" wrong <fact_id> "<what killed it, with the evidence>"
```

Raw form, if you need to write the replacement in the same breath:

```sh
sqlite3 -cmd ".timeout 5000" "$DB" "
  UPDATE fact SET status='disproven', evidence=evidence||' | DISPROVEN <date>: <what killed it>' WHERE id=<id>;
  INSERT INTO fact(scope,subject,claim,evidence,supersedes,source) VALUES('<scope>','<subj>','<claim>','<proof>',<id>,'<session>');"
```

## 3. Why recall missed it

Recall matches ordinary words against a row's **key**, not its body. Almost every miss is a
key-naming problem, and `brain-note.py` already refuses a key whose words would all be
stoplisted — so a miss on an existing row means the key was written before that guard, or the
words you typed are not the words in the key.

Measure it rather than guessing:

```sh
python3 "$BRAIN/brain-retrieve.py"                 # every row that cannot be found by its own key
python3 "$BRAIN/brain-retrieve.py" --new 14        # ...restricted to the last 14 days
```

**The ratio is the signal, not the count.** A jump concentrated in new rows means the last batch
was keyed badly; a jump across the whole corpus means recall itself regressed. Measured example:
3 of 10 new rows unfindable (30%) against a 1.6% baseline exposed two silent defects.

The key-naming rules, and the reasoning behind each, are in guide topic `09_lessons` —
`sqlite3 "$DB" "SELECT body FROM guide WHERE topic='09_lessons';"`. The short version:

- **A kebab-case key is the most retrievable shape there is.** A space-free key is treated as an
  identifier and matched per segment, so *every* word in it becomes a search term.
- Put the tool or vendor name in the key, and the word you would have **searched** for — not
  only the precise technical phrasing.
- Keep prose keys short. A key over 5 words needs two distinct query terms to match.
- Words buried in a path or identifier inside a *prose* key are invisible. Kebab the whole key.
- Never key a row on a file path alone. Avoid colloquialisms.

If a term is being swallowed as generic, check the stoplist before rekeying. Freeing concrete
technical nouns that had been stopped as English (`local`, `hook`, `table`, `repo`, `column`)
cut unreachable rows from 8/321 to 4/327. Free concrete nouns; never free common verbs. Your org
name is the opposite case — every path contains it, so it belongs in `BRAIN_STOP_EXTRA`.

## 4. Claim work so parallel agents do not collide

Subagents, background jobs and worktrees share one file and have no other shared state.

```sh
python3 "$BRAIN/brain-note.py" claim <scope> "<task>" [branch]   # warns if someone holds it
python3 "$BRAIN/brain-note.py" done <id> [artifacts]
```

Close it when done. A stale `open` row is worse than no row, because it makes the next agent
believe work is in flight — `brain-check.sh` flags any claim open over 14 days for exactly this
reason.

## 5. After ANY change, run the one check

```sh
bash "$BRAIN/brain-check.sh"
```

Integrity, an end-to-end seam probe on a throwaway brain, retrievability, staleness, stale
claims, the bounded accumulators, and whether every path the guide names still resolves. Exits
non-zero if anything is wrong. Run it after writing rows in bulk, after editing any hook, and
before trusting any number the brain reports.

Components correct against their own spec are still wrong together, so the probe in step 2 runs
one value all the way through — init, write, recall, capture, both harnesses. If you change the
engine, add the case that would have caught your bug **in the same turn**; a green suite proves
only what it tests, and mutating your fix back should turn it red.

## 6. Restructuring is sanctioned

The schema is yours to change whenever it stops fitting. When you change it: alter in one
transaction, bump `meta.schema_version`, append what and why to `guide` topic `06_changelog`,
update `02_query_recipes` if the query shape changed, and run `brain-check.sh`. Bias to fewer
tables; drop any table nothing has written to in a month.

If you change the `search` view's columns, re-run the check — `brain-recall.py` selects
`kind,key,body,verified_at,id,scope` from it.

**Guide topics 00–05 and 09 are seeded from files**, at `$BRAIN/guide/*.md`. Edit the *file* and
re-run `brain-init.py --guide`, or a package update overwrites your change. Topics created at
runtime (`06_changelog`, `08_current_advice`) have no file and are never overwritten.

Lessons about the brain itself go in `guide/09_lessons.md`, **not** in a `gotcha` row: rows
scoped `agent-brain` are excluded from the `search` view on purpose, so they are unreachable by
recall and you will never see them again.
