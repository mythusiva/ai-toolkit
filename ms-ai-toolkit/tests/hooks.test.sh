#!/usr/bin/env bash
# Guards the hook behaviour that fails SILENTLY -- a hook emitting nothing looks exactly like a
# hook with nothing to say, so none of this surfaces as an error in real use:
#   emit-prompt.sh      @PLUGIN@ resolution, install paths containing & or \, the missing-prompt guard
#   hook-critic-panel.sh  roster resolves only from the plugin, two-dir learnings merge,
#                         and the mark allowlist (a docs edit must not summon a panel)
#   hook-hard-requirements.sh  the gate opens only on a confirmed, fully-formed HR list, and
#                         Stop holds the turn to the snapshot exactly once
# Every assertion is mutation-checked: breaking the line it covers makes it fail.
# Run: dev-toolkit/tests/hooks.test.sh
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail=0
ok()  { echo "ok   $1"; }
bad() { echo "FAIL $1: $2"; fail=1; }
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
for tool in git jq; do command -v $tool >/dev/null || { echo "SKIP: $tool not on PATH"; exit 2; }; done

# --- emit-prompt.sh ---------------------------------------------------------
out=$(CLAUDE_PLUGIN_ROOT="$ROOT" bash "$ROOT/hooks/emit-prompt.sh" delegation-check)
case "$out" in
  *"$ROOT/prompts/plan-diagram.md"*) ok '@PLUGIN@ resolves to plugin root' ;;
  *) bad '@PLUGIN@ resolves' "no resolved path in output" ;;
esac
case "$out" in *@PLUGIN@*) bad 'no placeholder left' "@PLUGIN@ survived" ;; *) ok 'no placeholder left' ;; esac

# An & in the install path is a replacement-side metacharacter for BOTH sed and bash's
# ${v//pat/rep} (the latter from 5.2 on), so two successive fixes were silently wrong here.
# emit-prompt.sh splits on the token instead. Build a real dir so the file actually resolves.
weird="$tmp/a&b\\c"; mkdir -p "$weird/prompts"
printf 'see @PLUGIN@/prompts/x.md\n' > "$weird/prompts/probe.md"
out=$(CLAUDE_PLUGIN_ROOT="$weird" bash "$ROOT/hooks/emit-prompt.sh" probe)
[ "$out" = "see $weird/prompts/x.md" ] && ok 'metachar-hostile root (& and \) survives' \
  || bad 'metachar-hostile root' "got [$out] want [see $weird/prompts/x.md]"

# Assert on STDERR too: without the `[ -s "$f" ]` guard, cat still exits the script 0 with
# empty stdout, so stdout+rc alone cannot tell the guard from its absence -- only the leaked
# "No such file or directory" distinguishes them.
out=$(CLAUDE_PLUGIN_ROOT="$ROOT" bash "$ROOT/hooks/emit-prompt.sh" no-such-prompt 2>"$tmp/err"); rc=$?
err=$(cat "$tmp/err")
[ $rc -eq 0 ] && [ -z "$out" ] && [ -z "$err" ] && ok 'missing prompt: silent exit 0, no stderr' \
  || bad 'missing prompt' "rc=$rc out=[$out] err=[$err]"

# CLAUDE_PLUGIN_ROOT set-but-empty must fall back to the BASH_SOURCE-derived root, not "".
out=$(CLAUDE_PLUGIN_ROOT="" bash "$ROOT/hooks/emit-prompt.sh" delegation-stub)
[ -n "$out" ] && ok 'empty CLAUDE_PLUGIN_ROOT falls back' || bad 'empty CLAUDE_PLUGIN_ROOT' "emitted nothing"

# --- hook-critic-panel.sh ---------------------------------------------------
H="$tmp/home"; mkdir -p "$H/.claude"
repo="$tmp/repo"; mkdir -p "$repo"
( cd "$repo" && git init -q . && printf 'const a=1;\n' > a.ts && git add -A \
  && git -c user.email=t@t -c user.name=t commit -qm init && printf 'const a=1;\nconst b=2;\n' > a.ts )

panel() {  # $1 = session id -> prints the block reason
  HOME="$H" CLAUDE_PLUGIN_ROOT="$ROOT" bash "$ROOT/hooks/hook-critic-panel.sh" mark \
    <<<"{\"session_id\":\"$1\",\"tool_input\":{\"file_path\":\"$repo/a.ts\"}}" >/dev/null
  HOME="$H" CLAUDE_PLUGIN_ROOT="$ROOT" bash "$ROOT/hooks/hook-critic-panel.sh" panel \
    <<<"{\"session_id\":\"$1\",\"stop_hook_active\":false}" | jq -r '.reason // ""'
}

r=$(panel s1)
case "$r" in *"$ROOT/prompts/critic-panel.md"*) ok 'roster resolves to plugin' ;;
             *) bad 'roster resolves' "reason=[${r:0:120}]" ;; esac
case "$r" in *"$ROOT/critic-panel.d/learn"*) ok 'shipped learn seeds listed' ;;
             *) bad 'learn seeds' "seeds dir absent from reason" ;; esac
case "$r" in *"$H/.claude/critic-panel.d/learn/<critic>.md; feed"*) bad 'no ledger yet' "listed a \$HOME ledger that has no files" ;;
             *) ok 'absent $HOME ledger not listed as readable' ;; esac

mkdir -p "$H/.claude/critic-panel.d/learn"; echo '- x' > "$H/.claude/critic-panel.d/learn/security.md"
r=$(panel s2)
case "$r" in *"read $H/.claude/critic-panel.d/learn/<critic>.md"*) ok 'both learn dirs merged' ;;
             *) bad 'both learn dirs' "ledger missing once populated" ;; esac

# The roster has exactly ONE source: the plugin. Re-adding a $HOME fallback rung is invisible
# to every assertion above (they always pass a root that resolves on the first try), so prove
# the absence directly: a plugin root with no roster must yield NO panel even when tempting
# decoys exist at both legacy $HOME locations.
noroster="$tmp/noroster"; mkdir -p "$noroster/hooks" "$noroster/prompts"
cp "$ROOT/hooks/hook-critic-panel.sh" "$noroster/hooks/"
mkdir -p "$H/.claude/prompts"
echo 'DECOY ROSTER' > "$H/.claude/prompts/critic-panel.md"   # old "mirror/repo layout" rung
echo 'DECOY ROSTER' > "$H/.claude/critic-panel.md"           # old flat rung
HOME="$H" CLAUDE_PLUGIN_ROOT="$noroster" bash "$noroster/hooks/hook-critic-panel.sh" mark \
  <<<"{\"session_id\":\"s4\",\"tool_input\":{\"file_path\":\"$repo/a.ts\"}}" >/dev/null
r=$(HOME="$H" CLAUDE_PLUGIN_ROOT="$noroster" bash "$noroster/hooks/hook-critic-panel.sh" panel \
  <<<'{"session_id":"s4","stop_hook_active":false}')
[ -z "$r" ] && ok 'no $HOME roster fallback' || bad 'no $HOME roster fallback' "fell back: [${r:0:100}]"
rm -f "$H/.claude/prompts/critic-panel.md" "$H/.claude/critic-panel.md"

# --- hook-hard-requirements.sh ----------------------------------------------
# The gate's whole value is DENYING; a gate that quietly passes is indistinguishable from one
# that isn't wired, so each refusal reason gets its own case.
HR="$ROOT/hooks/hook-hard-requirements.sh"
gate() {  # allow == the hook emits nothing at all, so empty stdout must not reach jq
  local o; o=$(HOME="$H" bash "$HR" exit-gate <<<"{\"session_id\":\"$1\",\"tool_input\":{\"plan\":$2}}")
  [ -z "$o" ] && { echo allow; return; }
  printf '%s' "$o" | jq -r '.hookSpecificOutput.permissionDecision // "allow"'
}
GOOD='"## HARD REQUIREMENTS\nHR1: never log raw PAN | verify: grep -r pan src/ | wc -l == 0\n"'

[ "$(gate g1 '"just a plan with no rules"')" = "deny" ] && ok 'HR gate: no section -> deny' \
  || bad 'HR gate: no section' "expected deny"
[ "$(gate g2 "$GOOD")" = "deny" ] && ok 'HR gate: unconfirmed list -> deny' \
  || bad 'HR gate: unconfirmed' "expected deny without an AskUserQuestion marker"

# ask-mark must be selective: only a question actually about the rules opens the gate.
HOME="$H" bash "$HR" ask-mark <<<'{"session_id":"g3","tool_input":{"question":"which colour?"}}'
[ -f "$H/.claude/reqs-asked.d/g3" ] && bad 'HR ask-mark selective' "unrelated question opened the gate" \
  || ok 'HR ask-mark: unrelated question does not open the gate'
HOME="$H" bash "$HR" ask-mark <<<'{"session_id":"g4","tool_input":{"question":"confirm these hard requirements?"}}'
[ -f "$H/.claude/reqs-asked.d/g4" ] && ok 'HR ask-mark: naming hard requirements opens it' \
  || bad 'HR ask-mark' "marker not created"

[ "$(gate g4 "$GOOD")" = "allow" ] && ok 'HR gate: confirmed + well-formed -> allow' \
  || bad 'HR gate: valid plan' "expected allow"
grep -q '^HR1:' "$H/.claude/hard-reqs.d/g4" 2>/dev/null && ok 'HR gate: snapshots the agreed rules' \
  || bad 'HR snapshot' "no HR lines captured for Stop"

# An HR line with no verify: clause is the subtle one -- section and confirmation both present.
[ "$(gate g4 '"## HARD REQUIREMENTS\nHR1: never log raw PAN\n"')" = "deny" ] \
  && ok 'HR gate: missing verify: clause -> deny' || bad 'HR gate: no verify clause' "expected deny"

# Stop blocks once against the snapshot, then must not nag on the retry.
HOME="$H" bash "$HR" exit-gate <<<"{\"session_id\":\"g5\",\"tool_input\":{\"plan\":$GOOD}}" >/dev/null
cp "$H/.claude/reqs-asked.d/g4" "$H/.claude/reqs-asked.d/g5" 2>/dev/null || true
HOME="$H" bash "$HR" exit-gate <<<"{\"session_id\":\"g5\",\"tool_input\":{\"plan\":$GOOD}}" >/dev/null
d=$(HOME="$H" bash "$HR" stop-verify <<<'{"session_id":"g5","stop_hook_active":false}' | jq -r '.decision // ""')
[ "$d" = "block" ] && ok 'HR stop-verify: blocks on an unverified snapshot' || bad 'HR stop-verify' "got [$d]"
d2=$(HOME="$H" bash "$HR" stop-verify <<<'{"session_id":"g5","stop_hook_active":false}')
[ -z "$d2" ] && ok 'HR stop-verify: silent on the retry' || bad 'HR stop-verify retry' "blocked twice: [$d2]"


# Docs must not summon the panel; only code files.
printf '# hi\n' > "$repo/b.md"
HOME="$H" CLAUDE_PLUGIN_ROOT="$ROOT" bash "$ROOT/hooks/hook-critic-panel.sh" mark \
  <<<"{\"session_id\":\"s3\",\"tool_input\":{\"file_path\":\"$repo/b.md\"}}" >/dev/null
[ -f "$H/.claude/criticpanel-pending.d/s3" ] && bad '.md ignored' "markdown edit marked" || ok '.md ignored'

exit $fail
