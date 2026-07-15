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
    rm -f "$ddir/$sid"                                   # one panel per turn of code changes
    [ "$lines" -le 15 ] && tier="SMALL DIFF (~$lines changed lines): run principal + clean-arch ONLY; skip security/correctness unless the diff touches real logic or a trust boundary." || tier="FULL DIFF (~$lines changed lines): run the ALWAYS four."
    [ "$(printf '%s' "$in" | jq -r '.stop_hook_active // false')" = "true" ] && exit 0
    roster="$HOME/.claude/prompts/critic-panel.md"     # mirror/repo layout
    [ -s "$roster" ] || roster="$HOME/.claude/critic-panel.md"   # flat ~/.claude layout fallback
    [ -s "$roster" ] || exit 0                           # roster missing (misinstall) -> skip, don't block with an empty panel
    # Per-critic learning lives in learn/<critic>.md; host reads matching files itself.
    ldir="$HOME/.claude/critic-panel.d/learn"
    learn=""
    for f in "$ldir"/*.md; do [ -e "$f" ] && { learn=" Prior learnings per critic: read $ldir/<critic>.md and feed each into its matching critic prompt."; break; }; done
    jq -n --arg r "$roster" --arg l "$learn" --arg t "$tier" '{decision:"block", reason:("CRITIC PANEL: this turn changed code. " + $t + " Read the roster at " + $r + " and follow it (dispatch, token, and synthesis rules all live there)." + $l)}'
    ;;
esac
exit 0
