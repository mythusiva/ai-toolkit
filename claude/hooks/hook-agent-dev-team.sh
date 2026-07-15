#!/bin/bash
# Senior review panel, separate from the delegation hook.
# mark  (PostToolUse Edit|Write): a code file changed this turn -> touch a per-session marker.
# panel (Stop): if the turn changed code, block ONCE and hand the host the dev-team roster
#               (prompts/agent-dev-team.md) to dispatch as parallel advisory review agents.
# Advisory means: the block only forces the panel to RUN; findings never force a fix.
ddir="$HOME/.claude/devteam-pending.d"
in=$(cat)
sid=$(printf '%s' "$in" | jq -r '.session_id // "nosession"' 2>/dev/null)
sid=${sid//[^A-Za-z0-9_-]/_}

case "$1" in
  mark)
    fp=$(printf '%s' "$in" | jq -r '.tool_input.file_path // ""' 2>/dev/null)
    # code-only allowlist: docs/json/yaml edits should not summon the panel.
    # Add extensions here if a real code change is being missed.
    case "$fp" in
      *.js|*.jsx|*.ts|*.tsx|*.mjs|*.cjs|*.py|*.go|*.rb|*.java|*.kt|*.swift|*.rs|*.c|*.cc|*.cpp|*.h|*.hpp|*.cs|*.php|*.sql|*.sh|*.scala|*.vue)
        mkdir -p "$ddir"; touch "$ddir/$sid" 2>/dev/null ;;
    esac
    ;;
  panel)
    find "$ddir" -type f -mmin +240 -delete 2>/dev/null
    [ -f "$ddir/$sid" ] || exit 0
    rm -f "$ddir/$sid"                                   # one panel per turn of code changes
    [ "$(printf '%s' "$in" | jq -r '.stop_hook_active // false')" = "true" ] && exit 0
    roster=$(cat "$HOME/.claude/prompts/agent-dev-team.md" 2>/dev/null)
    [ -z "$roster" ] && exit 0                           # roster missing (misinstall) -> skip, don't block with an empty panel
    # Per-critic learning: each critic accumulates durable lessons in learn/<critic>.md.
    # Inject them so critics apply what past reviews taught; host appends new ones after synthesis.
    ldir="$HOME/.claude/agent-dev-team.d/learn"
    learn=$(for f in "$ldir"/*.md; do [ -e "$f" ] || continue; printf '### %s\n' "$(basename "$f" .md)"; cat "$f"; printf '\n'; done 2>/dev/null)
    jq -n --arg r "$roster" --arg l "$learn" '{decision:"block", reason:("DEV-TEAM PANEL: this turn changed code. Each critic prompt MUST start with the token DEV-TEAM-PANEL (exempts it from the plan gate). Dispatch each applicable critic as an independent parallel Agent unit (read-only, advisory), then synthesize one line per critic and stop. Do NOT skip because checks already passed: this is code-quality review, distinct from the verify gate.\n\n" + $r + (if $l == "" then "" else "\n\nPRIOR LEARNINGS (feed each block into its matching critic prompt): \n" + $l end))}'
    ;;
esac
exit 0
