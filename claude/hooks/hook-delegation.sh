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
in=$(cat)
sid=$(printf '%s' "$in" | jq -r '.session_id // "nosession"')
sid=${sid//[^A-Za-z0-9_-]/_}
is_sub=$(printf '%s' "$in" | jq -r 'has("agent_id")')

case "$1" in
  drift)
    [ "$is_sub" = "true" ] && exit 0
    jq -n --arg m "DELEGATION DRIFT CHECK: about to run this inline? If it's delegable execution (esp. the SAME op across N targets, or you already scouted and are now executing) that's N fully-specified haiku units via the Agent tool, run in parallel - NOT inline. Proceed inline ONLY if delegating, genuinely architectural, or the user asked for inline." \
      '{hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:$m}}'
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
    case "$resolved" in
      *[Hh]aiku*) ;;   # leaf: no marker, terminal
      *)               # interior node: allow agents of this type to delegate this session
        mkdir -p "$dir"
        at=$(printf '%s' "$in" | jq -r '.tool_input.subagent_type // "claude"')
        at=${at//[^A-Za-z0-9_-]/_}
        touch "$dir/${sid}__${at}" 2>/dev/null ;;
    esac
    [ -n "$m" ] && exit 0   # explicit model: nothing to rewrite
    printf '%s' "$in" | jq -c \
      '{hookSpecificOutput:{hookEventName:"PreToolUse",
        updatedInput:(.tool_input + {model:"haiku"}),
        additionalContext:"Delegated model defaulted to haiku. Escalate a genuinely complex, cross-file piece with model:sonnet (or model:opus/inherit for the hardest) -- those agents may decompose further; haiku cannot."}}'
    ;;
esac
exit 0
