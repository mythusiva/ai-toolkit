---
name: director
description: Run a long-lived "director" session that coordinates your other agent sessions, wakes on a schedule to look for work and brings every decision to you, and survives its own handoffs without losing rules or schedules. Use when the user asks to set up, start, run, tick, or hand off a director, a coordinator, or a manager session.
---

# Director

A director is one agent session whose job is coordination, not coding. It relays between you and
worker sessions, wakes every 30 minutes to find the next useful step toward the current goal, and
brings every fork (a decision with more than one option) to you. Like a shift lead with a binder: the binder (rules,
tick checklist, schedule, log) outlives any one shift, so a new director picks up exactly where the
last one stopped.

```
           system crontab                       you
               │ every 30 min                    │ chat / Matrix      
               ▼                                 ▼
        scripts/tick.sh ──agent-manager send──▶ DIRECTOR ──spawn/send──▶ worker sessions
               │ reads director.id                 │
               │                                   ├─ reads  rules.md, tick.md
               │                                   └─ writes handoff-log.md
               ▼
        $DIRECTOR_HOME/director.id  ◀── each new director writes its own id here
```

## The binder: `$DIRECTOR_HOME`

One folder (default `~/.director`) holds everything that must survive a handoff. Seed it from
`templates/` the first time:

```sh
export DIRECTOR_HOME=~/.director
mkdir -p "$DIRECTOR_HOME" && cp -n templates/*.md "$DIRECTOR_HOME/"
```

| File | Purpose | Who edits |
|---|---|---|
| `rules.md` | Standing hard rules. The user never restates one twice. | Director, the same turn the user states a rule |
| `tick.md` | The numbered checklist each wake-up runs | Director, when the routine changes |
| `schedule.md` | The only list of scheduled wake-ups | Director, the same turn a schedule changes |
| `handoff-log.md` | Append-only: one line per tick, one `## Handoff` section per handoff | Director |
| `director.id` | The current director's session id; the scheduler reads it | Each new director at startup |

## Startup (every new director, in order)

1. Read `rules.md`, then the **last** `## Handoff` section of `handoff-log.md`.
2. Write your own id: `agent-manager sessions --json | jq -r '.[]|select(.self==true)|.id' > "$DIRECTOR_HOME/director.id"`.
   The scheduler now wakes you, not your predecessor.
3. Check the system schedule matches `schedule.md` (`crontab -l`); add missing rows with
   `scripts/install-schedule.sh`.
4. Send your new id to every session the handoff lists as reporting to the director.
5. Read the predecessor's screen (`agent-manager read <old id>`) for anything the user typed after
   the handoff was written. Then the predecessor retires (see the `handoff` skill).
6. Work the handoff's open items.

## Every real user message

When the user states a new standing rule, append it to `rules.md` in the same turn, dated.
Scheduler wake-ups, pasted logs and session relays are not the user and don't count.

## Tick

Run `tick.md` top to bottom. The two invariants: **never just wait for relays** (each tick names and
does the next step toward the goal), and **log one line per tick** in `handoff-log.md` saying what
moved.

## Forks and the Matrix channel

Every fork goes to the user as a question (rules C2). The director never merges or posts on its
own; it executes what the user decides. An unanswered question goes on the handoff's open list as
`pending-q <topic>`, so a successor keeps asking.

Matrix (`scripts/mx.py`) is a plain second channel the user can use any time, not a mode. Each
tick runs `scripts/mx.py read`; answer the user there when they write there. Questions go to
Matrix only if the user asks for that.

## Scheduling

opencode has no in-session cron, so wake-ups come from the system crontab. `scripts/tick.sh`
reads `director.id` and queues the tick prompt with `agent-manager send`, which types it in only
once the director is idle. Because the id file changes at handoff, the schedule never has to be
moved between sessions, and two directors never both tick.

## Handoff

Use the `handoff` skill, plus:

1. Append a `## Handoff <date time> (<old id> -> successor)` section to `handoff-log.md`: open items,
   pending questions, sessions reporting to the director, anything in flight.
2. The successor's brief says: "You are the director. Run the director skill's Startup."
3. Retire only after the successor has written `director.id`
   (`cat "$DIRECTOR_HOME/director.id"` shows its id).

## Traps

- Archiving a worker session hides it but does not stop it. Kill, then archive. Check every tick.
- A rule the user stated only in chat dies with the session. Write it to `rules.md` that turn.
- An approval from a reviewer agent covers that exact proposal only. Never cite it to skip a
  later check, and never present it to the user as authority; show the evidence instead.
