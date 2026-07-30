#!/bin/bash
# PreToolUse gate for delegation. agent_id in stdin => the call came from a subagent.
# Delegation forms a tree whose leaves are the DEFAULT tier: main + agents spawned with an
# EXPLICIT non-haiku model may delegate; everything else is terminal. Default tier is sonnet
# (2026-07-28) and a defaulted sonnet is still a LEAF -- the right to delegate comes from the
# caller deliberately passing model:sonnet/opus/inherit, not from the resolved tier.
# Enforced by allow-markers that cap-model writes on explicit escalation, keyed by
# session + subagent_type.
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
    [ -f "$dir/${sid}__${at}" ] && exit 0                # caller was spawned with an explicit non-haiku model: interior node, may delegate
    rm -f "$(ls -t "$HOME/.claude/delegate-active.d"/d."$sid".* 2>/dev/null | head -1)"  # deny -> agent never runs -> drop the active-marker start just created (else it orphans, status bar shows phantom agents)
    jq -n '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:"Leaf agents may not delegate. Complete this work yourself. Only agents spawned with an EXPLICIT model (sonnet/opus/inherit) decompose further; the default tier is terminal."}}'
    ;;
  cap-model)
    # An OMITTED model resolves to sonnet (the default tier) and stays a LEAF. Explicit
    # opus/sonnet/inherit are deliberate escalations: they pass through AND earn the right
    # to delegate further. Explicit haiku = cheap leaf for trivial fully-specified units.
    m=$(printf '%s' "$in" | jq -r '.tool_input.model // ""')
    resolved=${m:-sonnet}          # default tier = sonnet (2026-07-28): quality lever, haiku is opt-in now
    p=$(printf '%s' "$in" | jq -r '.tool_input.prompt // ""')
    miss=""
    escalated=""
    # spec gate on EVERY tier (was haiku-only): a unit prompt must name files and a proving check.
    # No length minimum -- guidance now demands TERSE specs, and a complete spec can be one line;
    # length was only ever a proxy for the two substantive checks below.
    printf '%s' "$p" | grep -qiE 'verif|check|accept|expect|assert|prove|confirm' || miss="no proving check"
    printf '%s' "$p" | grep -qE '/[A-Za-z0-9_.-]+|[A-Za-z0-9_-]+\.[a-z]{2,4}\b' || miss="${miss:+$miss; }no file path"
    if printf '%s' "$p" | grep -qiE 'dump|paste the|quote the|list all|verbatim|entire file|all lines|full content'; then
      printf '%s' "$p" | grep -qiE 'verbatim|no placeholder|do not summar|do not truncat|every line|in full' || miss="${miss:+$miss; }data-return unit without a verbatim/no-placeholder guard"
    fi
    # Substantial work on an EXPLICIT haiku without a full spec is the retry-loop trigger -> sonnet.
    case "$resolved" in
      *[Hh]aiku*) [ -n "$miss" ] && [ "${#p}" -ge 500 ] && resolved="sonnet" && escalated="1" ;;
    esac
    # Allow-marker (right to delegate further) keys on an EXPLICIT non-haiku model only.
    # A DEFAULTED or auto-escalated sonnet stays a leaf -- otherwise every unspecified unit
    # becomes an interior node and nesting explodes.
    case "$m" in
      ""|*[Hh]aiku*) : ;;
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
    # Only inject the verbose peer-board block when another agent is live in this
    # session roster (count includes our own entry, so >=2 => a peer exists). Solo
    # delegations skip it cleanly -- telling a lone agent to coordinate is noise.
    # Limitation: the first agent of a parallel batch may see only itself and skip the
    # block; it still writes an outbox later peers can read. Upgrade to a barrier only if
    # coordinated parallel batches actually need every member boarded.
    peers=$(find "$cdir/roster" -type f 2>/dev/null | wc -l | tr -d ' ')
    haspeers=""; [ "${peers:-0}" -ge 2 ] && haspeers="1"
    warn=""
    [ -n "$miss" ] && [ -z "$escalated" ] && warn=" THIN SPEC ($miss): every unit needs exact files + expected result + proving check. Non-trivial unit -> output untrusted, respawn with a full spec."
    defnote=""
    [ -z "$m" ] && defnote="Model->sonnet (default tier; leaf, cannot delegate). Trivial + fully-specified -> model:haiku (cheaper); money/security/concurrency/deep logic -> model:opus (auto effort:low). Data-return: demand verbatim, no placeholders. Research claims: cite file:line."
    [ -n "$escalated" ] && defnote="Auto-escalated explicit haiku->sonnet: thin spec ($miss) on >=500 chars. Tighten spec (exact files + proving check) to keep it on haiku."
    # Sub-haiku local tier: when Gemma-4B is available locally, nudge the caller to run
    # units MORE trivial than haiku warrants (pure text transforms) through it for zero
    # Claude tokens. Cheap glob, only on DEFAULTED spawns (where trivial work lands now that
    # the default is sonnet). Advisory: the hook cannot run gemma as an Agent result, so the
    # caller invokes ${CLAUDE_PLUGIN_ROOT}/scripts/gemma-run.sh via Bash.
    case "${m:-default}" in
      default|*[Hh]aiku*)
        if command -v llama-server >/dev/null 2>&1 && \
           ls "$HOME"/.cache/huggingface/hub/models--ggml-org--gemma-4-E4B-it-GGUF/snapshots/*/gemma-*.gguf >/dev/null 2>&1; then
          defnote="$defnote GEMMA TIER: pure text transforms (summarize/extract/classify/reformat/count/rewrite, NO code judgment) -> no agent, run ${CLAUDE_PLUGIN_ROOT}/scripts/gemma-run.sh via Bash (zero tokens); verify output. Anything needing code reasoning or multi-file context stays on an agent."
        fi
        ;;
    esac
    eff=$(printf '%s' "$in" | jq -r '.tool_input.effort // ""')
    case "$resolved" in *[Oo]pus*) [ -z "$eff" ] && eff="low" ;; esac   # opus defaults to low reasoning effort (fast); explicit effort passes through
    # jq program below is wrapped in bash single quotes: it must contain NO single quote
    # (apostrophes included) or bash quoting breaks. Keep the injected help text quote-free.
    printf '%s' "$in" | jq -c \
      --arg model "$resolved" --arg tok "$tok" --arg cdir "$cdir" --arg atype "$atype" \
      --arg note "$defnote" --arg warn "$warn" --arg eff "$eff" --arg haspeers "$haspeers" '
      (.tool_input.prompt // "") as $p |
      (if $haspeers == "1" then
        ($p + "\n\nPEER BOARD: you are [" + $tok + "]. Write ONLY " + $cdir + "/msgs/" + $tok + ".md (append). Read peers: cat " + $cdir + "/msgs/*.md, roster: cat " + $cdir + "/roster/*. Use it to cross-check assumptions and align interfaces. No notifs, re-read. Never write another file there.")
       else $p end) as $np |
      {hookSpecificOutput:{hookEventName:"PreToolUse",
        updatedInput:(.tool_input + {model:$model, prompt:$np} + (if $eff=="" then {} else {effort:$eff} end)),
        additionalContext:($note + $warn)}}'
    ;;
  plan-clear)
    # UserPromptSubmit: each new user prompt wipes the ask marker -> per-turn re-ask.
    rm -f "$HOME/.claude/ask-asked.d/$sid" 2>/dev/null
    # explicit opt-out opens the ask gate for this turn
    if printf '%s' "$in" | jq -r '.prompt // ""' | grep -qiE 'skip questions|no questions|just do it|dont ask|do not ask|no need to ask'; then
      mkdir -p "$HOME/.claude/ask-asked.d"; touch "$HOME/.claude/ask-asked.d/$sid" 2>/dev/null
    fi
    ;;
  ask-mark)
    # PreToolUse on AskUserQuestion: scope was narrowed with the user this turn.
    mkdir -p "$HOME/.claude/ask-asked.d"
    touch "$HOME/.claude/ask-asked.d/$sid" 2>/dev/null
    ;;
  plan-mark)
    # PreToolUse on ExitPlanMode. ASK GATE: no plan may be presented until AskUserQuestion ran
    # this turn, or the plan carries an explicit NO QUESTIONS: <why>. Stops plans built on
    # invented assumptions. (The plan-approval marker it used to write died with the plan gate.)
    adir="$HOME/.claude/ask-asked.d"
    find "$adir" -type f -mmin +240 -delete 2>/dev/null
    if [ ! -f "$adir/$sid" ] && ! printf '%s' "$in" | jq -r '.tool_input.plan // ""' | grep -q 'NO QUESTIONS:'; then
      jq -n '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:"ASK GATE: narrow scope before planning. Call AskUserQuestion with 1-3 questions on what the prompt and the code do not settle: scope boundary, unstated choice between options, done-criteria, which of several files/patterns/tokens. Assume nothing. Then re-plan. Genuinely unambiguous -> put a line NO QUESTIONS: <why> in the plan."}}'
      exit 0
    fi
    ;;
  plan-gate)
    # Retired 2026-07-29: the plan gate blocked mutating|worktree delegation until a plan was
    # approved that turn, which throttled delegation itself -- the opposite of what this hook is
    # for. Planning is still expected (see delegation-check.md), just not hook-enforced.
    # Branch kept as a no-op so a stale settings.json wiring cannot fail closed.
    exit 0
    ;;
  stop-verify)
    # Closes the quality loop: a turn cannot end with unverified worker output.
    # Marker is touched by delegate-mark.sh on SubagentStop (a worker finished).
    find "$vdir" -type f -mmin +240 -delete 2>/dev/null
    [ -f "$vdir/$sid" ] || exit 0
    rm -f "$vdir/$sid"                                   # one block per batch of returns
    [ "$(printf '%s' "$in" | jq -r '.stop_hook_active // false')" = "true" ] && exit 0
    jq -n '{decision:"block", reason:"VERIFY GATE: workers returned this session. Verify EACH delegated unit -- host MAY run the checks inline (re-lint files, read diff, run proving command, screenshot vs design) or delegate a verify unit; independent verification wants a delegated unit. Cite the evidence per unit. Unverified or failing -> verify or dispatch a fix now. All verified -> restate evidence, one line/unit, then stop."}'
    ;;
esac
exit 0
