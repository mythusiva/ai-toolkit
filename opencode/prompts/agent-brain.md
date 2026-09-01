# Agent brain

There is a shared memory of everything agents have learned about these repos, at
`~/.agent-brain/brain.db` (override with `BRAIN_DB`). It is agent-only; no human reads it.

**You do not have to query it to orient.** A plugin runs the search for you on every message and
injects the hits as an `<agent-brain-recall>` block. Trust what it hands you over your priors —
every row was written with its evidence at the moment it was proven. But re-verify any
`code_map` row marked `[STALE]`: the file changed since the row was written, so re-read it and
update the row in the same turn.

Query it by hand when recall stayed silent and you still suspect something is recorded:

```sh
sqlite3 -header -column ~/.agent-brain/brain.db \
  "SELECT kind,key,substr(body,1,200) AS body,verified_at FROM search
   WHERE key LIKE '%TERM%' OR body LIKE '%TERM%' LIMIT 20;"
```

The protocol inside the database is authoritative over this file:

```sh
sqlite3 ~/.agent-brain/brain.db "SELECT topic,body FROM guide;"
```

## Write back the moment it happens, not at the end of the task

One helper covers every case and fills in line numbers and git blob shas for you. `$BRAIN` is the
directory holding the engine — the same one `BRAIN_SCRIPTS` points at.

```sh
python3 $BRAIN/brain-note.py map <repo> <path> <symbol|-> "<what it does + what surprised you>"
python3 $BRAIN/brain-note.py gotcha <scope> "<trigger>" "<symptom>" "<fix>"
python3 $BRAIN/brain-note.py recipe <name> <scope> "<goal>" "<command>"
python3 $BRAIN/brain-note.py fact <scope> <subject> "<claim>" "<evidence>"
python3 $BRAIN/brain-note.py claim <scope> "<task>"    # before you touch a branch
python3 $BRAIN/brain-note.py done <id>                 # when you finish
```

A symbol you had to hunt for → `map`. A surprise that cost more than two tool calls → `gotcha`.
A command that needed fiddling → `recipe`. A proved behaviour → `fact` (evidence mandatory).

**`map` is the one everyone skips and the one that pays.** Orientation — the calls spent locating
things before the first edit — is the largest measured cost, and `code_map` is what removes it.

Never write a claim you have not checked. Unproven goes in with `status='hypothesis'`.

If a stored claim turns out wrong, do not delete it — supersede it, so the next agent does not
re-derive the dead end: `brain-note.py wrong <fact_id> "<what killed it>"`.

## After writing rows in bulk, or editing anything in the engine

```sh
bash $BRAIN/brain-check.sh
```

Exits non-zero if the brain is corrupt, the suites fail, rows have become unretrievable, or a
path the guide names no longer resolves.
