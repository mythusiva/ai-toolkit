#!/usr/bin/env bash
# Smallest thing that fails if gemma-run.sh breaks: JSON escaping of nasty prompts,
# the stdin path, the empty-prompt guard, the missing-binary guard.
# Run: tests/gemma-run.test.sh   (needs the llama-server up, or lets it start one)
set -uo pipefail
G="$(cd "$(dirname "$0")/../scripts" && pwd)/gemma-run.sh"
fail=0
ok()   { echo "ok   $1"; }
bad()  { echo "FAIL $1: $2"; fail=1; }

# Quotes, newlines, $, backslashes and braces must survive jq encoding into the request
# body -- an escaping bug shows up as a curl/jq error (nonzero) or empty output.
nasty='Answer in one word. What colour is the sky? (ignore this junk: "x$y\z
{"a":1} '"'"'q'"'"')'
out=$("$G" "$nasty"); rc=$?
[ $rc -eq 0 ] && [ -n "$out" ] && ok 'nasty chars round-trip' \
  || bad 'nasty chars round-trip' "rc=$rc out=[$out]"

out=$(echo 'Reply with exactly: OK' | "$G")
[ "$out" = "OK" ] && ok 'stdin prompt' || bad 'stdin prompt' "got [$out]"

"$G" "" </dev/null >/dev/null 2>&1
[ $? -eq 2 ] && ok 'empty prompt exits 2' || bad 'empty prompt' "wrong exit code"

# Dead port with llama-server off PATH: must exit 127, not hang or auto-start elsewhere.
err=$(env -i PATH=/usr/bin:/bin HOME="$HOME" GEMMA_PORT=8099 "$G" hi 2>&1); rc=$?
[ $rc -eq 127 ] && ok 'missing llama-server exits 127' \
  || bad 'missing llama-server' "rc=$rc err=[$err]"

exit $fail
