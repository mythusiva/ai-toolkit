#!/bin/bash
# Shows "⇄ delegating: <model>×N" for THIS session while its delegations are in-flight; empty otherwise.
in=$(cat)
sid=$(printf '%s' "$in" | jq -r '.session_id // "nosession"' 2>/dev/null)
sid=${sid//[^A-Za-z0-9_-]/_}
dir="$HOME/.claude/delegate-active.d"
badge=""
if [ -d "$dir" ]; then
  find "$dir" -type f -mmin +60 -delete 2>/dev/null   # reap stragglers from a missed stop (global, harmless)
  # filename d.<sid>.<tier>.<model>.<rand> -> "<tier> <model>"; group by both, sort keeps L1 before L2.
  parts=$(ls "$dir" 2>/dev/null | grep -E "^d\.${sid}\." \
    | sed -E "s/^d\.${sid}\.([^.]+)\.(.+)\.[^.]+$/\1 \2/" | sort | uniq -c \
    | awk '{ if ($1>1) printf "%s:%s×%s · ", $2, $3, $1; else printf "%s:%s · ", $2, $3 }' | sed 's/ · $//')
  [ -n "$parts" ] && badge="⇄ delegating: $parts"
fi
printf '%s' "$badge"
