#!/bin/bash
# PreToolUse gate for delegation. agent_id in stdin => the call came from a subagent.
# Delegation forms a tree whose leaves are haiku: main + explicitly-escalated
# (sonnet/opus/inherit) agents may delegate; haiku agents are terminal and may not.
# Enforced by allow-markers that cap-model writes whenever a non-haiku child is spawned,
# keyed by session + subagent_type.
#
# Ceiling: markers key on (session, agent_type), not per-agent-instance. If the SAME
# agent_type is spawned at two tiers in one session (e.g. a haiku AND a sonnet
# general-purpose), they share a marker and the haiku one is also allowed to delegate.
# Rare; upgrade to a per-agent_id map only if it bites.
dir="$HOME/.claude/delegator.d"
vdir="$HOME/.claude/verify-pending.d"
in=$(cat)
sid=$(printf '%s' "$in" | jq -r '.session_id // "nosession"')
sid=${sid//[^A-Za-z0-9_-]/_}
is_sub=$(printf '%s' "$in" | jq -r 'has("agent_id")')

case "$1" in
  drift)
    [ "$is_sub" = "true" ] && exit 0                     # workers run shell freely; host cannot
    jq -n '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:"Host is plan+research only: no Bash. Use Read/Grep/Glob/Explore for research; everything that RUNS -- builds, tests, git, migrations, screenshots, verification proving-checks -- is a delegated Agent unit. Need a command run? Delegate it (haiku by default)."}}'
    ;;
  readonly)
    [ "$is_sub" = "true" ] && exit 0                     # subagents (the workers) may write
    jq -n '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:"Host is plan+research only: no Edit/Write. Every mutation is a delegated Agent unit (haiku by default). Host reads, decomposes, delegates, and confirms worker-reported verification evidence; workers write."}}'
    ;;
  block-nested)
    [ "$is_sub" = "true" ] || exit 0                     # main session always delegates
    at=$(printf '%s' "$in" | jq -r '.agent_type // "claude"')
    at=${at//[^A-Za-z0-9_-]/_}
    find "$dir" -type f -mmin +120 -delete 2>/dev/null   # reap stragglers from a missed cleanup (interior agent >2h loses its marker; acceptable)
    [ -f "$dir/${sid}__${at}" ] && exit 0                # caller is a sonnet/opus interior agent: may delegate
    jq -n '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:"Haiku (leaf) agents may not delegate. Complete this work yourself. Only sonnet/opus/inherit agents decompose further; delegation stops at haiku."}}'
    ;;
  cap-model)
    # Only an OMITTED model defaults to haiku. Explicit opus/sonnet/inherit are deliberate
    # escalations for complex work -- they pass through AND earn the right to delegate further.
    m=$(printf '%s' "$in" | jq -r '.tool_input.model // ""')
    resolved=${m:-haiku}
    miss=""
    case "$resolved" in
      *[Hh]aiku*)
        # spec gate: a haiku leaf prompt must carry files, a proving check, and enough detail.
        # Warn-only (heuristic; escalate to deny if thin specs keep slipping through).
        p=$(printf '%s' "$in" | jq -r '.tool_input.prompt // ""')
        [ "${#p}" -lt 200 ] && miss="under 200 chars"
        printf '%s' "$p" | grep -qiE 'verif|check|accept|expect|assert|prove|confirm' || miss="${miss:+$miss; }no proving check"
        printf '%s' "$p" | grep -qE '/[A-Za-z0-9_.-]+|[A-Za-z0-9_-]+\.[a-z]{2,4}\b' || miss="${miss:+$miss; }no file path"
        ;;
      *)               # interior node: allow agents of this type to delegate this session
        mkdir -p "$dir"
        at=$(printf '%s' "$in" | jq -r '.tool_input.subagent_type // "claude"')
        at=${at//[^A-Za-z0-9_-]/_}
        touch "$dir/${sid}__${at}" 2>/dev/null ;;
    esac
    warn=""
    [ -n "$miss" ] && warn=" THIN SPEC ($miss): a haiku leaf needs exact files, expected result, and a proving check in its prompt. If this unit is non-trivial, treat its output as untrusted and respawn with a full spec."
    if [ -n "$m" ]; then
      [ -z "$warn" ] && exit 0
      jq -n --arg w "${warn# }" '{hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:$w}}'
      exit 0
    fi
    printf '%s' "$in" | jq -c --arg w "$warn" \
      '{hookSpecificOutput:{hookEventName:"PreToolUse",
        updatedInput:(.tool_input + {model:"haiku"}),
        additionalContext:("Model defaulted to haiku (leaf; cannot delegate). Escalate genuine cross-file work with model:sonnet (opus/inherit hardest only)." + $w)}}'
    ;;
  stop-verify)
    # Closes the quality loop: a turn cannot end with unverified worker output.
    # Marker is touched by delegate-mark.sh on SubagentStop (a worker finished).
    find "$vdir" -type f -mmin +240 -delete 2>/dev/null
    [ -f "$vdir/$sid" ] || exit 0
    rm -f "$vdir/$sid"                                   # one block per batch of returns
    [ "$(printf '%s' "$in" | jq -r '.stop_hook_active // false')" = "true" ] && exit 0
    jq -n '{decision:"block", reason:"VERIFY GATE: workers returned this session. Host cannot run checks itself (plan+research only) -- verification is its own delegated Agent unit. For EACH delegated unit, cite the verify-unit evidence (lint output, diff read, proving command result, screenshot vs design). Unverified or failing -> dispatch a verify or fix unit now. All verified -> restate the evidence, one line per unit, then stop."}'
    ;;
esac
exit 0
