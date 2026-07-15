# ai-toolkit

Personal Claude Code config: hooks, prompts, and commands that mirror the
`~/.claude` layout so they drop straight in.

## `claude/`

```
claude/
  settings.json          # hook wiring — the source of truth
  hooks/
    delegate-mark.sh        # tracks in-flight delegations per session/tier/model
    hook-delegation.sh      # drift nudge + haiku-leaf enforcement + model cap
    hook-agent-dev-team.sh  # senior review panel: fires at Stop on code changes
  prompts/
    delegation-check.md   # injected every turn (via UserPromptSubmit hook)
    agent-dev-team.md     # review-panel roster (cat by the dev-team Stop hook)
    lean-speak-style.md   # injected every turn while lean-speak is toggled on
  commands/
    lean-speak.md         # /lean-speak toggle
```

### What it does

- **Delegation** — nudges Claude to decompose work into small parallel subagents,
  defaults spawned agents to `haiku`, and enforces a delegation tree whose leaves
  (haiku agents) can't delegate further. `hooks/hook-delegation.sh` gates the
  `Agent` tool; `hooks/delegate-mark.sh` bookkeeps under `~/.claude/*.d`.
- **Agent dev-team** — on any code change, a senior review panel fires at Stop:
  parallel read-only critics (principal, clean-arch, security, correctness +
  conditional backend/frontend/test/perf/api) review the diff and report.
  Advisory (never auto-fixes); each critic accumulates durable lessons under
  `~/.claude/agent-dev-team.d/learn/`. Roster in `prompts/agent-dev-team.md`.
- **lean-speak** — terse, token-lean reply style. Off by default; `/lean-speak`
  toggles it by creating/removing `~/.claude/lean-speak.on`.

## Install

Requires `jq` (only for the settings merge).

```sh
C="$HOME/.claude"
mkdir -p "$C/hooks" "$C/prompts" "$C/commands"
cp claude/hooks/*.sh   "$C/hooks/"   && chmod +x "$C/hooks"/*.sh
cp claude/prompts/*.md "$C/prompts/"
cp claude/commands/*.md "$C/commands/"

# merge our hook entries into any existing settings.json
[ -f "$C/settings.json" ] || echo '{}' > "$C/settings.json"
cp "$C/settings.json" "$C/settings.json.bak"
jq -s '.[0] as $cur | .[1].hooks as $add
  | $cur | .hooks = (($cur.hooks // {}) as $h
      | reduce ($add|keys_unsorted[]) as $k ($h; .[$k]=(($h[$k]//[])+$add[$k])))' \
  "$C/settings.json.bak" claude/settings.json > "$C/settings.json"
```

Restart Claude Code. Paths in `settings.json` use `$HOME/.claude/...`, so they
resolve on any machine. Runtime dirs (`delegate-active.d`, `delegator.d`)
self-create.

## Usage

- `/lean-speak` — toggle terse mode on/off.
- Delegation hooks run automatically; no command needed.
