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
    exit 0
    ;;
  readonly)
    exit 0
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
    p=$(printf '%s' "$in" | jq -r '.tool_input.prompt // ""')
    miss=""
    escalated=""
    case "$resolved" in
      *[Hh]aiku*)
        # spec gate: a haiku leaf prompt must carry files, a proving check, and enough detail.
        [ "${#p}" -lt 200 ] && miss="under 200 chars"
        printf '%s' "$p" | grep -qiE 'verif|check|accept|expect|assert|prove|confirm' || miss="${miss:+$miss; }no proving check"
        printf '%s' "$p" | grep -qE '/[A-Za-z0-9_.-]+|[A-Za-z0-9_-]+\.[a-z]{2,4}\b' || miss="${miss:+$miss; }no file path"
        if printf '%s' "$p" | grep -qiE 'dump|paste the|quote the|list all|verbatim|entire file|all lines|full content'; then
          printf '%s' "$p" | grep -qiE 'verbatim|no placeholder|do not summar|do not truncat|every line|in full' || miss="${miss:+$miss; }data-return unit without a verbatim/no-placeholder guard"
        fi
        # Substantial work handed to haiku without a full spec is the retry-loop trigger.
        # Auto-escalate to fast opus (effort low, set below) -- one-shot beats a haiku retry loop.
        [ -n "$miss" ] && [ "${#p}" -ge 500 ] && resolved="opus" && escalated="1"
        ;;
    esac
    case "$resolved" in
      *[Hh]aiku*) : ;;
      *) mkdir -p "$dir"
         at=$(printf '%s' "$in" | jq -r '.tool_input.subagent_type // "claude"')
         at=${at//[^A-Za-z0-9_-]/_}
         touch "$dir/${sid}__${at}" 2>/dev/null ;;
    esac
    # Peer comms: give the child a PRIVATE outbox no one else writes -> zero overwrite risk, no locks.
    # Shared-nothing board: every agent reads all peer outboxes but writes only its own file.
    cdir="$HOME/.claude/agent-comms.d/$sid"
    mkdir -p "$cdir/roster" "$cdir/msgs" 2>/dev/null
    find "$HOME/.claude/agent-comms.d" -type f -mmin +240 -delete 2>/dev/null
    find "$HOME/.claude/agent-comms.d" -type d -empty -mmin +240 -delete 2>/dev/null
    tok=$(basename "$(mktemp "$cdir/roster/XXXXXX" 2>/dev/null)" 2>/dev/null)
    atype=$(printf '%s' "$in" | jq -r '.tool_input.subagent_type // "claude"')
    task=$(printf '%s' "$in" | jq -r '.tool_input.prompt // ""' | tr '\n\t' '  ' | head -c 80)
    [ -n "$tok" ] && printf '%s | %s\n' "$atype" "$task" > "$cdir/roster/$tok"
    warn=""
    [ -n "$miss" ] && [ -z "$escalated" ] && warn=" THIN SPEC ($miss): a haiku leaf needs exact files, expected result, and a proving check in its prompt. If this unit is non-trivial, treat its output as untrusted and respawn with a full spec."
    defnote=""
    [ -z "$m" ] && defnote="Model defaulted to haiku (leaf; cannot delegate). Too weak or a task dragging through retries -> model:opus (effort auto-set to low = fast, one-shot); genuine multi-file cross-file work -> model:sonnet; hardest only -> opus medium+/inherit. Data-return units (dump/quote/list) must demand verbatim output with NO placeholders/summarizing; treat any summarized or placeholdered return as lossy and re-request or cross-check. Load-bearing research claims must quote source (file:line); verify against the actual source before acting on them."
    [ -n "$escalated" ] && defnote="Auto-escalated haiku -> opus (effort low) because the spec was thin ($miss) on a substantial prompt (>=500 chars) -- one-shot opus beats a haiku retry loop. To keep it on haiku, tighten the spec (exact files + a proving check); to control the tier, pass model explicitly."
    eff=$(printf '%s' "$in" | jq -r '.tool_input.effort // ""')
    case "$resolved" in *[Oo]pus*) [ -z "$eff" ] && eff="low" ;; esac   # opus defaults to low reasoning effort (fast); explicit effort passes through
    # jq program below is wrapped in bash single quotes: it must contain NO single quote
    # (apostrophes included) or bash quoting breaks. Keep the injected help text quote-free.
    printf '%s' "$in" | jq -c \
      --arg model "$resolved" --arg tok "$tok" --arg cdir "$cdir" --arg atype "$atype" \
      --arg note "$defnote" --arg warn "$warn" --arg eff "$eff" '
      (.tool_input.prompt // "") as $p |
      ($p + "\n\n--- PEER COMMS (session-shared, always-on) ---\n"
          + "You are agent [" + $tok + "] (type: " + $atype + "). Other agents this session collaborate through a shared board.\n"
          + "Board: " + $cdir + "\n"
          + "  - YOUR outbox (write ONLY here; you are the sole writer): " + $cdir + "/msgs/" + $tok + ".md\n"
          + "    append a note:  echo YOUR_MESSAGE >> " + $cdir + "/msgs/" + $tok + ".md\n"
          + "  - PEERS: read all with  cat " + $cdir + "/msgs/*.md   |   who is live:  cat " + $cdir + "/roster/*\n"
          + "Coordinate freely: cross-check assumptions, share partial results, align on shared interfaces. Address a peer by their [token].\n"
          + "No push notifications -- re-read msgs/*.md when you need the latest from a peer. NEVER write a file that is not your own outbox.") as $np |
      {hookSpecificOutput:{hookEventName:"PreToolUse",
        updatedInput:(.tool_input + {model:$model, prompt:$np} + (if $eff=="" then {} else {effort:$eff} end)),
        additionalContext:($note + $warn)}}'
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
