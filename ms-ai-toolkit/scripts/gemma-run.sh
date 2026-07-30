#!/usr/bin/env bash
# Sub-haiku local tier: run one trivial text-transform prompt through Gemma 4 E4B
# for ZERO Claude tokens. For work below what a haiku agent warrants --
# summarize / extract / classify / reformat / count / regex-style rewrite -- never
# code judgment (4B model). Prompt from $1 or stdin; clean model output on stdout.
#   gemma-run.sh "Extract every TODO line from: $(cat foo.js)"
#   echo "Classify sentiment: ..." | gemma-run.sh
# Hits a persistent llama-server instead of loading the 7.5GB model per call
# (measured 0.4s vs 3s). Install llama-server.plist to keep it up across reboots;
# otherwise the first call after boot starts it and pays the load once.
set -euo pipefail

HOST=${GEMMA_HOST:-127.0.0.1}
PORT=${GEMMA_PORT:-8080}
REPO=${GEMMA_REPO:-ggml-org/gemma-4-E4B-it-GGUF}
CTX=${GEMMA_CTX:-8192}
NTOK=${GEMMA_NTOK:-1024}
TEMP=${GEMMA_TEMP:-0}          # text transforms want determinism, not creativity
URL="http://$HOST:$PORT"
log="$HOME/.claude/gemma.log"           # exchange log: tail -f ~/.claude/gemma.log
srvlog="$HOME/.claude/llama-server.log"

prompt=${1:-}
[ -n "$prompt" ] || prompt=$(cat)
[ -n "$prompt" ] || { echo "empty prompt" >&2; exit 2; }

if ! curl -sf --max-time 2 "$URL/health" >/dev/null 2>&1; then
  command -v llama-server >/dev/null 2>&1 \
    || { echo "llama-server not on PATH (brew install llama.cpp)" >&2; exit 127; }
  echo "gemma: starting llama-server ($REPO), first load takes ~30s" >&2
  # Outlives this script (reparented to launchd) so later calls find it warm.
  nohup llama-server -hf "$REPO" --host "$HOST" --port "$PORT" \
    -ngl 99 -c "$CTX" --flash-attn on --no-ui -t 8 \
    --chat-template-kwargs '{"enable_thinking":false}' >>"$srvlog" 2>&1 &
  for _ in $(seq 1 120); do
    curl -sf "$URL/health" >/dev/null 2>&1 && break
    sleep 1
  done
  curl -sf --max-time 2 "$URL/health" >/dev/null 2>&1 \
    || { echo "llama-server did not come up; see $srvlog" >&2; exit 1; }
fi

# Surface in the delegating-status badge while running: reuse the Agent active-marker
# convention (d.<sid>.<tier>.<model>.XXXXXX) statusline.sh parses -> shows "L0:gemma".
sid=${CLAUDE_CODE_SESSION_ID:-nosession}; sid=${sid//[^A-Za-z0-9_-]/_}
adir="$HOME/.claude/delegate-active.d"; mkdir -p "$adir" 2>/dev/null
marker=$(mktemp "$adir/d.${sid}.L0.gemma.XXXXXX" 2>/dev/null) || marker=""
# Record the task in the marker so you can see what gemma is working on:
#   cat ~/.claude/delegate-active.d/d.*.gemma.*
[ -n "$marker" ] && printf 'gemma | %s' "$(printf '%s' "$prompt" | tr '\n\t' '  ' | cut -c1-160)" > "$marker"
trap 'rm -f "$marker"' EXIT

req=$(jq -n --arg p "$prompt" --argjson n "$NTOK" --argjson t "$TEMP" \
  '{messages:[{role:"user",content:$p}],max_tokens:$n,temperature:$t}')
resp=$(curl -sS --fail-with-body --max-time 600 "$URL/v1/chat/completions" \
  -H 'Content-Type: application/json' -d "$req") \
  || { printf '%s\n' "$resp" >&2; exit 1; }

answer=$(jq -r '.choices[0].message.content | gsub("^\\s+|\\s+$";"")' <<<"$resp")
printf '\n=== %s\n--- prompt: %s\n--- answer: %s\n' \
  "$(date +%FT%T)" "${prompt:0:400}" "$answer" >> "$log"
printf '%s\n' "$answer"
