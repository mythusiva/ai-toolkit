#!/usr/bin/env bash
# Prints AWAY or PRESENT. AWAY = no real user message for AFK_IDLE seconds (default 2 h)
# AND a desktop dialog went unanswered for AFK_DIALOG seconds (default 9 min).
# The director writes `date +%s > $DIRECTOR_HOME/last-human` on every real user message.
set -u
home=${DIRECTOR_HOME:-$HOME/.director}
idle_limit=${AFK_IDLE:-7200}
dialog=${AFK_DIALOG:-540}
last=$(cat "$home/last-human" 2>/dev/null || echo 0)
idle=$(( $(date +%s) - last ))
(( idle < idle_limit )) && { echo "PRESENT (last message ${idle}s ago)"; exit 0; }

msg="Director: you have been quiet for a while. It will act alone within its away rules unless you click I am here."
if command -v osascript >/dev/null; then
  r=$(osascript -e "display dialog \"$msg\" buttons {\"I am here\"} default button 1 giving up after $dialog" 2>/dev/null)
  [[ -n $r && $r != *"gave up:true"* ]] && here=1 || here=0
elif command -v zenity >/dev/null; then
  zenity --question --title=Director --text="$msg" --ok-label="I am here" --timeout="$dialog" 2>/dev/null && here=1 || here=0
else
  here=0
fi
if (( here )); then date +%s > "$home/last-human"; echo "PRESENT (clicked I am here)"; else echo "AWAY (idle ${idle}s, dialog unanswered)"; fi
