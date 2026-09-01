# agent-brain

A SQLite file agents read before they grep and write to the moment they learn something. It
removes **orientation cost** — the tool calls an agent spends locating things before its first
edit, median 15 across 251 sessions. Costs one 45ms query per prompt, injected automatically.

Runs on **Claude Code** and **opencode** from the same engine. Nothing to configure: it defaults
to `~/.agent-brain/brain.db`.

```
     your prompt
          │
          ▼
   ┌──────────────┐   words in the prompt        ┌───────────────┐
   │ brain-recall │ ──────────────────────────►  │   brain.db    │
   │              │ ◄──────────────────────────  │               │
   └──────┬───────┘   matching rows, git-verified│  fact         │
          │                                      │  code_map     │
          ▼  <agent-brain-recall> injected       │  gotcha       │
     the model works                             │  recipe       │
          │                                      │  decision     │
          ▼  turn ends                           │  work_log     │
   ┌──────────────┐   did it learn and not write?│  thread       │
   │ brain-capture│ ──────────────────────────►  │  guide  ◄─────┼── guide/*.md
   └──────┬───────┘                              └───────▲───────┘
          │  "you owe a code_map row: <command>"         │
          ▼                                              │
     the model writes ──── brain-note.py ────────────────┘
```

**Recall** runs unconditionally and decides by data: a skill only fires when the model already
suspects the database has something, which is the judgement it cannot make at turn 1. **Capture**
fires on *evidence*, at most once per session — it converted 4 of 4 independent sessions into
writes while the matching skill was invoked zero times.

## Install

Claude Code gets it with the plugin — the hooks are already wired. Then, once:

```sh
python3 "$CLAUDE_PLUGIN_ROOT/brain/brain-init.py"
```

opencode discovers plugins with the glob `{plugin,plugins}/*.{ts,js}` — the `.js` extension is
load-bearing, a `.mjs` there is silently never loaded. Link the plugin and the protocol prompt,
then point it at the engine:

```sh
mkdir -p ~/.config/opencode/plugin ~/.config/opencode/prompts
ln -s "$PWD/opencode/plugin/agent-brain.js"   ~/.config/opencode/plugin/
ln -s "$PWD/opencode/prompts/agent-brain.md"  ~/.config/opencode/prompts/
export BRAIN_SCRIPTS="$PWD/ms-ai-toolkit/brain"   # unnecessary if the repo's opencode/
python3 "$PWD/ms-ai-toolkit/brain/brain-init.py"  # dir is itself the symlink target
```

## Configuration

Every one of these is optional.

| Variable | Default | Set it when |
|---|---|---|
| `BRAIN_DB` | `~/.agent-brain/brain.db` | you want the file somewhere else |
| `BRAIN_HOME` | `~/.agent-brain` | you want the marker dirs elsewhere |
| `BRAIN_STOP_EXTRA` | — | **your org name goes here.** Every path contains it, so it matches everything and carries no signal |
| `BRAIN_REPO_ROOT` | ask `git` | all your checkouts sit under one directory (`~/src`) |
| `BRAIN_SCRIPTS` | probed | opencode cannot find the engine beside its config |
| `BRAIN_DEBUG` | — | `1` to log every opencode plugin decision to stderr |

## The commands

| Command | What it does |
|---|---|
| `brain-init.py` | Create or upgrade the database; seed `guide` from `guide/*.md`. Idempotent |
| `brain-note.py` | Write a row. Fills in line numbers and git blob shas; refuses an unretrievable key |
| `brain-check.sh` | **The one health command.** Integrity, both suites, retrievability, staleness, stale claims, bounded accumulators, path resolution |
| `brain-retrieve.py` | Which rows cannot be found by their own key. The ratio is the signal, not the count |
| `brain-selftest.py` | 42 checks: init → write → recall → capture, both harnesses, on a throwaway brain |

## Before you change any of this

Read `guide/09_lessons.md` first: 31 monitoring passes, 27 defects, **every one silent** —
components reported success while doing nothing, while deleting work, and while reporting
catastrophe, all printing the same cheerful line. The content held up (9 of 9 hand-verified
facts); the machinery around it rots. Add the case that would have caught your bug in the same
turn, and check that mutating the fix turns it red.

## Appendix: what is deliberately not here

- **Health metrics and the daily snapshot.** Ten metrics, three of them small-sample enough to
  swing 20 points on one session. Useful with 500 rows of history behind them, noise before that.
- **The stream tables' collectors** (Slack/GitHub/Jira readers). The `thread` table ships,
  because `state='declined'` plus a `verdict` is the one thing no upstream system records; the
  browser automation that filled it was specific to one machine.
- **A regression suite asserting specific rows.** The suite this replaces asserted particular
  keys and would fail on day one of a new install. `brain-selftest.py` builds its own corpus
  instead, which is why it proves the mechanism rather than the data.
- **A Stop hook that can block, in opencode.** opencode has no blocking equivalent, so a nudge
  raised at `session.idle` is stashed and injected at the top of the next turn. Nothing ever
  calls `session.prompt()` on its own: an autonomous turn nobody asked for costs tokens and
  trains you to disable the plugin.
