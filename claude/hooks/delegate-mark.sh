#!/bin/bash
# PreToolUse(Agent): start -> add a marker tagged with this session + model.
# SubagentStop: stop -> remove one marker for THIS session.
# Filename d.<session>.<model>.<rand>; dir of files = in-flight delegations, scoped per session.
dir="$HOME/.claude/delegate-active.d"
mkdir -p "$dir"
in=$(cat)
sid=$(printf '%s' "$in" | jq -r '.session_id // "nosession"' 2>/dev/null)
sid=${sid//[^A-Za-z0-9_-]/_}   # filename-safe; strips any dot so field delimiters stay clean
case "$1" in
  start) m=$(printf '%s' "$in" | jq -r '.tool_input.model // "haiku"' 2>/dev/null)   # omitted model defaults to haiku, same rule as cap-model
         m=${m//[^A-Za-z0-9_-]/_}
         # tier: L1 = spawned by main, L2 = spawned by any subagent (nested). Depth >2 folds into L2
         # (hook stdin exposes no parent chain/self-id to chain true depth; upgrade only if harness adds a SubagentStart parent link).
         tier=$(printf '%s' "$in" | jq -r 'if has("agent_id") then "L2" else "L1" end' 2>/dev/null)
         mktemp "$dir/d.${sid}.${tier}.${m}.XXXXXX" >/dev/null ;;
  stop)  f=$(ls "$dir"/d."${sid}".* 2>/dev/null | head -1)   # only this session's markers
         [ -n "$f" ] && rm -f "$f"
         mkdir -p "$HOME/.claude/verify-pending.d"           # worker finished -> Stop hook demands verification evidence
         touch "$HOME/.claude/verify-pending.d/$sid" ;;
esac
