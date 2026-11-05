#!/usr/bin/env bash
# Called by the system crontab. Queues a prompt for whichever session is the director now.
# usage: tick.sh "<prompt>"
set -eu
home=${DIRECTOR_HOME:-$HOME/.director}
id=$(cat "$home/director.id" 2>/dev/null) || { echo "no $home/director.id" >&2; exit 1; }
# --from: the scheduler is not a session, so the director's reply has nowhere to go and none is expected.
agent-manager send "$id" "$1" --from scheduler
