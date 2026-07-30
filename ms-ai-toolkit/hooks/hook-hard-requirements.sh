#!/bin/bash
# HARD REQUIREMENTS gate. Every plan must carry an explicit, user-confirmed list of rules that
# may never be broken, each with its own verification -- and the turn cannot end until each one
# is restated with evidence.
#
# Flow: plan-start (inject elicitation) -> ask-mark (AskUserQuestion about requirements ran)
#       -> exit-gate (deny ExitPlanMode until section + confirmation both exist; snapshot HR lines)
#       -> stop-verify (block Stop once until every snapshotted HR is verified).
#
# Markers age out at 240m, matching hook-delegation.sh.
adir="$HOME/.claude/reqs-asked.d"
rdir="$HOME/.claude/hard-reqs.d"
in=$(cat)
sid=$(printf '%s' "$in" | jq -r '.session_id // "nosession"')
sid=${sid//[^A-Za-z0-9_-]/_}

FORMAT='Format, verbatim, inside the plan:

## HARD REQUIREMENTS
HR1: <rule that must never be broken> | verify: <command / test / observable proving it held>
HR2: ...

One line per rule. Every line needs its own verify: clause -- a thing that can be run or looked at, not "review the code".'

case "$1" in
  plan-start)
    # PreToolUse on EnterPlanMode: first thing every plan does is pin down the hard rules.
    jq -n --arg fmt "$FORMAT" '{hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:(
      "HARD REQUIREMENTS FIRST. Before designing anything, work out with the user the short list of rules this change may never break -- the ones where a violation means the work is wrong no matter how good the rest is. Look for them in: what the user said must/must not happen, trust boundaries (authz, money, data loss), backwards compatibility and existing callers, the design or spec if one was given, and the repo conventions that apply here.\n\nDraft 2-5 candidates from the prompt and the code, then confirm them with ONE AskUserQuestion (say the words hard requirements in it) so the user can cut, add, or reword. Do not invent rules the user never implied, and do not pad the list -- a rule that is merely nice-to-have belongs in the plan body, not here.\n\n" + $fmt)}}'
    ;;
  ask-mark)
    # PreToolUse on AskUserQuestion: only a question actually about the hard rules opens the gate.
    if printf '%s' "$in" | jq -r '.tool_input // {} | tostring' \
       | grep -qiE 'hard requirement|hard rule|non-negotiable|must never|never break|invariant'; then
      mkdir -p "$adir"; touch "$adir/$sid" 2>/dev/null
    fi
    ;;
  exit-gate)
    # PreToolUse on ExitPlanMode: section AND confirmation, both, or no plan.
    find "$adir" -type f -mmin +240 -delete 2>/dev/null
    plan=$(printf '%s' "$in" | jq -r '.tool_input.plan // ""')
    miss=""
    printf '%s' "$plan" | grep -qi 'HARD REQUIREMENTS' || miss="no HARD REQUIREMENTS section"
    printf '%s' "$plan" | grep -qE '^ *HR[0-9]+:' || miss="${miss:+$miss; }no HR<n>: lines"
    printf '%s' "$plan" | grep -E '^ *HR[0-9]+:' | grep -qv 'verify:' && miss="${miss:+$miss; }an HR line has no verify: clause"
    [ -f "$adir/$sid" ] || miss="${miss:+$miss; }the list was never confirmed with the user (AskUserQuestion naming hard requirements)"
    if [ -n "$miss" ]; then
      jq -n --arg miss "$miss" --arg fmt "$FORMAT" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:(
        "HARD REQUIREMENTS GATE: " + $miss + ".\n\nEvery plan carries the rules it may never break, confirmed with the user, each with its own check. Draft 2-5 from the prompt, the code, the trust boundaries and the existing callers; confirm them in ONE AskUserQuestion that uses the words hard requirements; then put them in the plan and re-present.\n\n" + $fmt)}}'
      exit 0
    fi
    # Snapshot the agreed rules so Stop can hold the turn to them even after the plan scrolls away.
    mkdir -p "$rdir"
    find "$rdir" -type f -mmin +240 -delete 2>/dev/null
    printf '%s' "$plan" | grep -E '^ *HR[0-9]+:' > "$rdir/$sid" 2>/dev/null
    ;;
  stop-verify)
    # Stop: the turn cannot end with an unverified hard requirement. One block per approved plan.
    [ -f "$rdir/$sid" ] || exit 0
    [ "$(printf '%s' "$in" | jq -r '.stop_hook_active // false')" = "true" ] && exit 0
    reqs=$(cat "$rdir/$sid")
    rm -f "$rdir/$sid"
    jq -n --arg reqs "$reqs" '{decision:"block", reason:(
      "HARD REQUIREMENTS VERIFY: these were agreed with the user and may not be broken:\n\n" + $reqs +
      "\n\nRun each verify: clause now -- the command, the test, the observable. Then restate every HR on one line: HR<n> PASS/FAIL + the evidence (command output, file:line, screenshot). Any FAIL -> fix it and re-check before stopping; do not renegotiate a rule the user confirmed. Work not started yet (plan rejected or deferred) -> say exactly that in one line and stop.")}'
    ;;
esac
exit 0
