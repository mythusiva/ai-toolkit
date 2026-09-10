#!/bin/bash
# HARD REQUIREMENTS gate. Every plan must carry an explicit, user-confirmed list of rules that
# may never be broken, each with its own verification -- and the turn cannot end until each one
# is restated with evidence.
#
# Flow: plan-start (inject elicitation) -> ask-mark (AskUserQuestion about requirements ran)
#       -> exit-gate (deny ExitPlanMode until section + confirmation both exist; snapshot HR lines)
#       -> stop-verify (block Stop once until every snapshotted HR is verified).

#
# Every user-facing message here is read by a junior dev who has never seen the gate before:
# what the gate is, what is missing, what happens next, then a concrete example. Not prose.
#
# Markers age out at 240m, matching hook-delegation.sh.
adir="$HOME/.claude/reqs-asked.d"
rdir="$HOME/.claude/hard-reqs.d"
in=$(cat)
sid=$(printf '%s' "$in" | jq -r '.session_id // "nosession"')
sid=${sid//[^A-Za-z0-9_-]/_}

FORMAT='EXAMPLE -- this is what the plan has to contain:

## HARD REQUIREMENTS
HR1: existing /v1 callers keep working unchanged | verify: npm test -- api/v1
HR2: no endpoint returns another user'"'"'s rows   | verify: curl as user B -> 403

RULES OF THE FORMAT
- One line per rule, numbered HR1, HR2, ... Shape: <the rule> | verify: <the check>.
- The verify: half must be something that can be RUN or LOOKED AT -- a command, a test name,
  a log line, a screenshot. "review the code" is not a check.
- 2-5 rules. A merely nice-to-have belongs in the plan body, not here.'

case "$1" in
  plan-start)
    # PreToolUse on EnterPlanMode: first thing every plan does is pin down the hard rules.
    jq -n --arg fmt "$FORMAT" '{hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:(
      "HARD REQUIREMENTS FIRST -- before designing anything.\n\nA hard requirement is a rule where breaking it makes the work wrong no matter how good the rest is. Find them in: what the user said must or must not happen; trust boundaries (authz, money, data loss); backwards compatibility and existing callers; the design or spec if one was given; the repo conventions that apply here.\n\nSteps:\n1. Draft 2-5 candidates from the prompt and the code.\n2. Confirm them in ONE AskUserQuestion that says the words hard requirements, so the user can cut, add or reword.\n3. Put the agreed list in the plan.\nDo not invent rules the user never implied, and do not pad the list.\n\n" + $fmt)}}'
    ;;
  ask-mark)
    # PreToolUse on AskUserQuestion: only a question actually about the rules/boundary opens each
    # gate. One call may legitimately settle both, so the two patterns are tested independently.
    body=$(printf '%s' "$in" | jq -r '.tool_input // {} | tostring')
    if printf '%s' "$body" \
       | grep -qiE 'hard requirement|hard rule|non-negotiable|must never|never break|invariant'; then
      mkdir -p "$adir"; touch "$adir/$sid" 2>/dev/null
    fi
    ;;
  exit-gate)
    # PreToolUse on ExitPlanMode: section AND confirmation, both, or no plan.
    find "$adir" -type f -mmin +240 -delete 2>/dev/null
    plan=$(printf '%s' "$in" | jq -r '.tool_input.plan // ""')

    miss=""
    printf '%s' "$plan" | grep -qi 'HARD REQUIREMENTS' || miss="no ## HARD REQUIREMENTS section"
    printf '%s' "$plan" | grep -qE '^ *HR[0-9]+:' || miss="${miss:+$miss; }no HR<n>: lines"
    printf '%s' "$plan" | grep -E '^ *HR[0-9]+:' | grep -qv 'verify:' && miss="${miss:+$miss; }an HR line has no verify: clause"
    [ -f "$adir/$sid" ] || miss="${miss:+$miss; }the list was never confirmed with the user (an AskUserQuestion naming hard requirements)"
    if [ -n "$miss" ]; then
      jq -n --arg miss "$miss" --arg fmt "$FORMAT" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:(
        "HARD REQUIREMENTS GATE: " + $miss + ".\n\nWHAT THIS GATE IS\nBefore a plan is approved it must list the rules this change may never break, and how each one gets checked. A hard requirement is a rule where breaking it makes the work wrong no matter how good the rest is. The plan above was blocked, not shown to the user.\n\nWHAT TO DO NEXT (the user only has to answer one question)\n1. Draft 2-5 candidate rules from the prompt, the code, the trust boundaries (authz, money, data loss) and the existing callers.\n2. Ask ONE question, using the words hard requirements, so the user can cut, add or reword them.\n3. Put the agreed list in the plan and re-present it.\n\n" + $fmt)}}'
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
      "HARD REQUIREMENTS VERIFY: the turn cannot end until each of these agreed rules has been checked.\n\nWHAT THIS GATE IS\nThe user confirmed these rules when the plan was approved. The turn ends once each one has been re-checked with evidence, not once the code is written:\n\n" + $reqs +
      "\n\nWHAT TO DO NEXT\n1. Run each verify: clause -- the actual command, test or observable. Do not assert from memory.\n2. Restate every rule on one line: HR<n> PASS/FAIL + the evidence (command output, file:line, screenshot).\n3. Any FAIL -> fix it and re-check before stopping. Do not renegotiate a rule the user confirmed.\n\nNothing was built (plan rejected or deferred) -> say exactly that in one line and stop.")}'
    ;;
esac
exit 0
