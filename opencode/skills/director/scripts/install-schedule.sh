#!/usr/bin/env bash
# Replaces the director block in the user's crontab with the rows of $DIRECTOR_HOME/schedule.md.
# Idempotent: rerun after every edit to schedule.md. Run it from the installed skill
# (~/.config/opencode/skills/director/scripts/) so the crontab survives moving the repo.
set -eu
home=${DIRECTOR_HOME:-$HOME/.director}
tick="$(cd "$(dirname "$0")" && pwd)/tick.sh"
path=$(dirname "$(command -v agent-manager)")
block=$(awk -F'|' -v tick="$tick" -v home="$home" -v path="$path" '
  /^\| *[0-9]+ *\|/ {
    cron=$3; gsub(/^ *`|` *$/, "", cron)
    prompt=$4; gsub(/^ +| +$/, "", prompt); gsub(/\$DIRECTOR_HOME/, home, prompt); gsub(/"/, "\\\"", prompt)
    printf "%s PATH=%s:/usr/bin:/bin DIRECTOR_HOME=%s %s \"%s\" # director\n", cron, path, home, tick, prompt
  }' "$home/schedule.md")
{ crontab -l 2>/dev/null | grep -v '# director$' || true; echo "$block"; } | crontab -
crontab -l | grep -c '# director$' | xargs echo "director rows installed:"
