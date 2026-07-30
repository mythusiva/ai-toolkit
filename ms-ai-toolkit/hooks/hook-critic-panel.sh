#!/bin/bash
# Senior review panel, separate from the delegation hook.
# mark  (PostToolUse Edit|Write): a code file changed this turn -> touch a per-session marker.
# panel (Stop): if the turn changed code, block ONCE and hand the host the critic-panel
#               roster to dispatch as parallel advisory review agents.
# Advisory means: the block only forces the panel to RUN; findings never force a fix.
ddir="$HOME/.claude/criticpanel-pending.d"
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
        # Only review files inside a git working tree (skip ~/.claude tooling, scratch, etc.)
        git -C "$(dirname "$fp")" rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
        mkdir -p "$ddir"; printf '%s\n' "$fp" >> "$ddir/$sid" 2>/dev/null ;;
    esac
    ;;
  panel)
    find "$ddir" -type f -mmin +240 -delete 2>/dev/null
    [ -f "$ddir/$sid" ] || exit 0
    # sum changed lines across the turn's files -> tier (small diffs skip the opus pair).
    lines=0
    while IFS= read -r fp; do
      [ -n "$fp" ] || continue
      d=$(dirname "$fp")
      n=$(git -C "$d" diff --numstat HEAD -- "$fp" 2>/dev/null | awk '{s+=$1+$2} END{print s+0}')
      [ "$n" = 0 ] && [ -f "$fp" ] && ! git -C "$d" ls-files --error-unmatch "$fp" >/dev/null 2>&1 && n=$(wc -l < "$fp" 2>/dev/null)
      lines=$((lines + ${n:-0}))
    done < <(sort -u "$ddir/$sid")
    files=$(sort -u "$ddir/$sid" | tr '\n' ' ')
    rm -f "$ddir/$sid"                                   # one panel per turn of code changes
    # Tier names no roster content on purpose -- critic names in a shell string drift (they did).
    # lines=0 = couldn't measure (committed mid-turn), NOT small -> default FULL.
    if [ "$lines" -gt 0 ] && [ "$lines" -le 15 ]; then tier="SMALL DIFF (~$lines changed lines)"; else tier="FULL DIFF (~$lines changed lines)"; fi
    [ "$(printf '%s' "$in" | jq -r '.stop_hook_active // false')" = "true" ] && exit 0
    root="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"  # same resolution as emit-prompt.sh
    roster="$root/prompts/critic-panel.md"
    [ -s "$roster" ] || exit 0                           # roster missing (misinstall) -> skip, don't block with an empty panel
    # Per-critic learning lives in learn/<critic>.md; host reads matching files itself.
    # Seeds ship read-only with the plugin; the live ledger the panel appends to is under $HOME.
    learn=""
    for ldir in "$root/critic-panel.d/learn" "$HOME/.claude/critic-panel.d/learn"; do
      ls "$ldir"/*.md >/dev/null 2>&1 && learn="$learn read $ldir/<critic>.md;"
    done
    [ -n "$learn" ] && learn=" Prior learnings per critic:$learn feed each into its matching critic prompt (append NEW learnings to $HOME/.claude/critic-panel.d/learn/<critic>.md)."
    jq -n --arg r "$roster" --arg l "$learn" --arg t "$tier" --arg f "$files" '{decision:"block", reason:("CRITIC PANEL: this turn changed code. " + $t + ". Files changed THIS turn: " + $f + "-- scope every critic to these, do not re-review hunks from earlier turns. Read the roster at " + $r + " and follow it (roster/dispatch/SCALE/token/synthesis rules all live there; apply its SCALE section for this tier)." + $l)}'
    ;;
esac
exit 0
