---
name: handoff
description: Hand the current work to a fresh agent session instead of letting this one grow huge or auto-compact. Use when context passes ~300K tokens, when the user says "hand off", "start fresh", "new session", or before a long task outgrows this session. Writes durable notes, spawns the successor with a self-contained brief, and retires this session.
---

# Handoff

A long session re-sends its whole context on every step, so cost and latency climb with every
turn, and auto-compaction throws detail away without telling you. A deliberate handoff keeps the
detail: you write down what matters, a new session starts clean, and the old one stops.

```
old session                         new session
-----------                         -----------
1 finish the current atomic step
2 write durable notes  ───────────▶ reads them
3 spawn(name, brief)   ───────────▶ 4 confirms it has what it needs
5 archive-self + kill-self               carries on
```

## When

- Context is **~300K tokens** or more. Don't wait for the model's limit: the handoff itself needs
  room, and a compaction mid-handoff loses the very detail you were saving.
- Re-check every ~100K tokens after that; if you are still here, hand off now.
- The user asks for a fresh session, or the next task is unrelated to this session's theme.

## Session verbs (agent-manager)

| Verb | Command |
|---|---|
| who am I | `agent-manager sessions --json \| jq -r '.[]\|select(.self==true)\|.id'` |
| spawn | `agent-manager spawn --name "<theme>" --directory "<repo>" --prompt "<brief>"` |
| message | `agent-manager send <id> "<text>"` |
| retire self | `agent-manager archive-self && agent-manager kill-self` |

Archiving alone hides a session but keeps it running (and any schedule it owns keeps firing).
Always kill as well.

## Steps

1. **Finish the atomic step** you are in. Never hand off mid-edit or mid-migration.
2. **Write durable notes first.** Anything that lives only in this conversation goes to the
   project's notes (memory store, `NOTES.md`, the feature's plan folder, a handoff log). The new
   session cannot see this conversation.
3. **Spawn the successor** with the same broad theme as its name and a brief that stands alone:

   | Brief field | What goes in it |
   |---|---|
   | Goal | The user's goal, verbatim, plus any standing done-condition |
   | State | What is done, with proof (commit sha, PR link, test output) |
   | Where | Repo, branch, worktree path, running processes or servers |
   | Next | The very next step, then the rest in order |
   | Open | Questions waiting on the user, with the options already offered |
   | Notes | Keys or paths of the notes written in step 2 |
   | Close | "Confirm you have what you need, then I retire." |

4. **Wait for the successor to confirm** (`agent-manager wait <id> --until idle`, then
   `agent-manager read <id>`). Answer its questions once.
5. **Tell the user** the successor's name in one line.
6. **Retire**: `agent-manager archive-self && agent-manager kill-self`. Don't linger answering
   messages; forward stragglers to the successor once, then stop.

## Traps

- A brief that says "see above" or "as discussed": the successor has no "above". Paste it.
- Forgetting scheduled work this session owns (crons, watchers): list it in the brief and stop it
  here only after the successor has re-armed it.
- Handing off with uncommitted edits in a shared checkout: commit to a WIP branch or name the
  dirty files in the brief.
