# ms-ai-toolkit

Personal Claude Code workflow plugin: delegation gates, hard-requirement plan gates, an
advisory senior-review critic panel, two reply-style modes, and a handful of investigation
skills. Replaces the old hand-copied `claude/` bundle in this repo — nothing is copied into
`~/.claude/` any more.

## Install

```
/plugin marketplace add mythusiva/ai-toolkit
/plugin install ms-ai-toolkit@ms-ai
```

Restart Claude Code, then `/plugin` to confirm it's enabled. Hooks, commands, prompts and
skills wire themselves up — no `settings.json` editing, no configuration. Update later with
`/plugin update ms-ai-toolkit@ms-ai`.

One command after install, to create the agent brain:

```
python3 "$CLAUDE_PLUGIN_ROOT/brain/brain-init.py"
```

## Already hand-installed the old `claude/` bundle? Clean up first

The old README told you to `cp` scripts into `~/.claude/` and merge hook entries into
`~/.claude/settings.json`. Leaving those in place while the plugin is enabled fires every
hook **twice** — two `delegate-mark.sh start` per sub-agent, two critic-panel blocks at Stop.

In `~/.claude/settings.json`, remove every hook entry invoking these; the plugin supplies all
of them:

| Remove entries calling | Events |
|---|---|
| `delegate-mark.sh` | `PreToolUse:Agent`, `SubagentStop` |
| `hook-delegation.sh` | `PreToolUse:Agent\|Bash\|Edit\|Write\|AskUserQuestion\|ExitPlanMode`, `Stop`, `UserPromptSubmit` |
| `hook-critic-panel.sh` | `PostToolUse:Edit\|Write`, `Stop` |
| `hook-hard-requirements.sh` | `PreToolUse:EnterPlanMode\|ExitPlanMode\|AskUserQuestion`, `Stop` |
| `cat`-ing `delegation-check.md` / `delegation-stub.md` / `ponytail-*.md` / `lean-speak-style.md` | `SessionStart`, `UserPromptSubmit` |

Keep anything unrelated. If `statusLine` points at `~/.claude/statusline.sh`, repoint it — see
*Status line* below. Your `~/.claude/` state carries over untouched (learnings ledger,
sentinels); the old `~/.claude/*.sh` and `*.md` copies are then dead and can be deleted.

## What you get

| Piece | Fires on | What it does |
|---|---|---|
| `brain/brain-recall.py` | UserPromptSubmit | Queries the agent brain for words in your prompt and injects any hits, git-verified and labelled `[STALE]` if the file moved. Silent when it has nothing. ~45ms |
| `brain/brain-capture.py` | Stop | If the session shows evidence of learning and the brain did not change, blocks once with the exact write commands. Evidence-triggered, at most once per session |
| `brain/brain-guard.py` | SessionStart | ~36ms health canary. Silent unless the brain is corrupt, empty, rotting, or holding a stale work claim |
| `hooks/hook-delegation.sh` | Agent, Bash, Edit/Write, AskUserQuestion, ExitPlanMode, Stop | Manager-mode delegation: caps sub-agent models by tier, blocks nested delegation from leaf agents, guards read-only agents, marks the ask/plan gates, and demands verification evidence at Stop |
| `hooks/delegate-mark.sh` | Agent start / SubagentStop | Tracks in-flight sub-agents (feeds the status line and the verify gate) |
| `hooks/hook-critic-panel.sh` | Edit/Write, Stop | If the turn changed code, blocks once and hands over the critic roster to dispatch as parallel advisory reviewers. Advisory: findings never force a fix |
| `hooks/hook-hard-requirements.sh` | EnterPlanMode, ExitPlanMode, AskUserQuestion, Stop | Every plan must carry a short list of rules the change may never break, each with its own verify clause, confirmed with you. Denies `ExitPlanMode` until the list exists and was confirmed, then holds the turn at Stop until each one is restated with evidence |
| `hooks/emit-prompt.sh` | — | Helper: prints a `prompts/*.md` file with its `@PLUGIN@` placeholders resolved |
| `/ms-ai-toolkit:lean-speak` | manual | Toggles the terse reply style |

Prompts injected each session/turn live in `prompts/`: `delegation-check.md` (full rules, at
SessionStart), `delegation-stub.md` (per-turn reminder), `ponytail-mode.md` /
`ponytail-stub.md`, `lean-speak-style.md`, `critic-panel.md` (the roster), `plan-diagram.md`
(ASCII diagram format).

The brain is a whole subsystem with its own docs, environment variables and health command —
see [`brain/README.md`](brain/README.md). Nothing to configure to start: it defaults to
`~/.agent-brain/brain.db`, and the same engine drives the opencode plugin.

Skills in `skills/` load on demand, by description: `agent-brain` (work *on* the brain — retire a
wrong fact, diagnose why recall missed, claim work, restructure), `feature-deep-dive` (investigate an
existing feature to runtime depth, not just structure), `figma-prefetch` and `figma-export`
(read a Figma file once into a local cache / export screens + metadata),
`google-slides-editing` (drive Slides through the Chrome DevTools MCP), and
`update-coding-guidelines` (fold a newly-learned pattern into the right repo's guidelines
file).

Tests live in `tests/`, outside `hooks/` and `scripts/` (those hold runtime entrypoints only):
`tests/hooks.test.sh` covers hook path-resolution, `tests/gemma-run.test.sh` the local-model
wrapper.

## State the plugin reads or writes under `~/.claude/`

The plugin ships no state. These are created on demand and are yours to keep:

- `delegate-active.d/`, `delegator.d/`, `verify-pending.d/`, `plan-approved.d/`,
  `ask-asked.d/`, `criticpanel-pending.d/`, `agent-comms.d/`, `reqs-asked.d/`,
  `hard-reqs.d/` — per-session runtime markers, self-cleaning (they age out at 240m)
- `critic-panel.d/learn/<critic>.md` — your growing per-critic learnings. Seeds ship in the
  plugin at `critic-panel.d/learn/`; the panel reads both and appends only to yours
- `critic-panel.d/severity.md` — optional calibration ledger: finding classes you've already
  skipped or downgraded. The panel drops or demotes matches, so it's the real severity bar
- `lean-speak.on` — sentinel, present = lean-speak ON (`/ms-ai-toolkit:lean-speak` toggles it)
- `ponytail.off` — sentinel, present = ponytail mode OFF

## Optional extras

**Status line.** Plugins can't set `statusLine`, so wire `hooks/statusline.sh` yourself for the
active-agent counter. In `~/.claude/settings.json`:

```json
"statusLine": {
  "type": "command",
  "command": "bash \"$HOME/.claude/plugins/cache/ms-ai/ms-ai-toolkit/<version>/hooks/statusline.sh\""
}
```

**Local Gemma tier.** `scripts/gemma-run.sh` runs a local Gemma-4B for zero-token text
transforms (summarize/extract/classify/reformat). The delegation rules only mention it when
the model is actually reachable, so it stays invisible until you set up `llama-server`
(`brew install llama.cpp`). `scripts/llama-server.plist` is a LaunchAgent that keeps it warm —
symlink it into `~/Library/LaunchAgents/` and `launchctl bootstrap` it; the header comment has
the exact commands.

**Ponytail.** `prompts/ponytail-mode.md` is a condensed "lazy senior dev" ruleset. It overlaps
the standalone `ponytail` plugin — running both gives you both injections; disable one.

## Changing the rules

The installed copy under `~/.claude/plugins/cache/` is overwritten on every plugin update, so
edits there don't survive. Tune the rules by editing `ms-ai-toolkit/` in this repo and bumping
`version` in both `ms-ai-toolkit/.claude-plugin/plugin.json` and the entry in
`.claude-plugin/marketplace.json` at the repo root.
