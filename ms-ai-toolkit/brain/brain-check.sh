#!/usr/bin/env bash
# The one command that exercises the whole brain. Run it after writing rows in bulk, after
# editing any hook, and before trusting any number the brain reports.
#
# Every step is written to be FORCED to admit failure. Success is the default output of any
# component: three commands here once reported success doing nothing, one reported success while
# deleting work, and an audit exited 0 while reporting total catastrophe. All printed the same
# cheerful line. So each step below prints its evidence, and the problems print LAST -- the
# last thing on screen should be the problem, or it gets ignored by its own author.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB="${BRAIN_DB:-${BRAIN_HOME:-$HOME/.agent-brain}/brain.db}"
STATE="${BRAIN_HOME:-$HOME/.agent-brain}"
PY="${PYTHON:-python3}"
FAILED=()
WARNED=()

step() { printf '\n== %s\n' "$1"; }
fail() { FAILED+=("$1"); printf '   FAIL %s\n' "$1"; }
warn() { WARNED+=("$1"); printf '   warn %s\n' "$1"; }

if [ ! -f "$DB" ]; then
  echo "no brain at $DB"
  echo "create it with: $PY \"$HERE/brain-init.py\""
  exit 1
fi
echo "brain-check  db=$DB  state=$STATE"

step "1. integrity"
IC=$(sqlite3 "$DB" "PRAGMA integrity_check;" 2>&1)
echo "   integrity_check: $IC"
[ "$IC" = "ok" ] || fail "sqlite integrity_check: $IC"
FK=$(sqlite3 "$DB" "PRAGMA foreign_key_check;" 2>&1)
[ -z "$FK" ] || fail "foreign_key_check: $FK"
JM=$(sqlite3 "$DB" "PRAGMA journal_mode;" 2>&1)
echo "   journal_mode: $JM"
[ "$JM" = "wal" ] || warn "journal_mode is $JM, not wal - concurrent agents will block each other"

step "2. end-to-end seam probe (own temp brain, does not touch yours)"
if OUT=$("$PY" "$HERE/brain-selftest.py" 2>&1); then
  echo "   $(echo "$OUT" | tail -1)"
else
  echo "$OUT" | sed 's/^/   /'
  fail "brain-selftest.py - the pipeline is broken, not just the data"
fi

step "2b. opencode transport (skipped if node is not installed)"
# The engine is shared, so a defect in the Python shows up in both harnesses -- but the JS
# transport that carries it is opencode's alone and has its own way to break.
OCTEST="$HERE/../../opencode/tests/agent-brain.test.mjs"
if ! command -v node >/dev/null 2>&1; then
  echo "   skipped: node not on PATH"
elif [ ! -f "$OCTEST" ]; then
  echo "   skipped: opencode plugin not present in this install"
elif OUT=$(node "$OCTEST" 2>&1); then
  echo "   $(echo "$OUT" | tail -1)"
else
  echo "$OUT" | sed 's/^/   /'
  fail "opencode plugin probe - recall or capture is not reaching the model in opencode"
fi

step "3. retrievability (can a row be found by its own key?)"
# The ratio is the signal, not the count. A jump concentrated in NEW rows means the last batch
# was keyed badly; a jump across the whole corpus means recall itself regressed.
ALL=$("$PY" "$HERE/brain-retrieve.py" --quiet 2>&1); RC=$?
echo "   all:  $ALL"
NEW=$("$PY" "$HERE/brain-retrieve.py" --quiet --new 14 2>&1)
echo "   14d:  $NEW"
[ $RC -eq 0 ] || fail "more than 10% of rows cannot be retrieved by their own key - see guide 09_lessons"

step "4. what may have rotted"
STALE=$(sqlite3 "$DB" "SELECT count(*) FROM stale;")
TOTAL=$(sqlite3 "$DB" "SELECT count(*) FROM search;")
echo "   stale: $STALE of $TOTAL searchable rows"
[ "$STALE" -gt $((TOTAL / 4)) ] && warn "over a quarter of the corpus is past its freshness window - sweep: SELECT * FROM stale;"
DIS=$(sqlite3 "$DB" "SELECT count(*) FROM fact WHERE status='hypothesis' AND verified_at < date('now','-30 day');")
[ "$DIS" -gt 0 ] && warn "$DIS hypotheses older than 30d were never confirmed or disproven"

step "5. stale claims (a stale open row makes the next agent think work is in flight)"
OPEN=$(sqlite3 -separator ' | ' "$DB" \
  "SELECT id,scope,task FROM work_log WHERE status IN ('open','blocked') AND started_at < datetime('now','-14 day');")
if [ -n "$OPEN" ]; then
  echo "$OPEN" | sed 's/^/   /'
  warn "$(echo "$OPEN" | wc -l | tr -d ' ') claim(s) open over 14 days - close with: brain-note.py done <id>"
else
  echo "   none open over 14 days"
fi

step "6. bounded accumulators (none of these break at scale, which is why nobody notices)"
for d in capture.d delivered.d collide.d health.d; do
  if [ -d "$STATE/$d" ]; then
    N=$(find "$STATE/$d" -type f | wc -l | tr -d ' ')
    printf '   %-12s %s files\n' "$d" "$N"
    [ "$N" -gt 800 ] && warn "$STATE/$d has $N files - the self-prune keeps 400, so it is not running"
  fi
done
CHG=$(sqlite3 "$DB" "SELECT COALESCE(length(body),0) FROM guide WHERE topic='06_changelog';")
echo "   06_changelog ${CHG:-0} chars"
[ "${CHG:-0}" -gt 6000 ] && warn "06_changelog is ${CHG} chars - trim it, promote durable lessons to 09_lessons"
HR=$(sqlite3 "$DB" "SELECT count(*) FROM health WHERE day < date('now','-180 day');")
[ "$HR" -gt 0 ] && warn "$HR health rows older than 180d - DELETE FROM health WHERE day < date('now','-180 day');"

step "7. every path the guide and the scripts name actually resolves"
# A doc that must be hand-synchronised with a live system is wrong by default. This step is why
# the guide files carry @SCRIPTS@ placeholders instead of literal paths.
MISS=0
for f in brainlib.py brain-init.py brain-note.py brain-recall.py brain-capture.py \
         brain-retrieve.py brain-selftest.py; do
  [ -f "$HERE/$f" ] || { fail "missing script: $HERE/$f"; MISS=1; }
done
# Expand ~ and $HOME before testing. The first version of this check grepped a bare
# /.../brain-*.py and reported 6 false failures on paths that all existed, because it matched
# from the slash AFTER the tilde. Verify the verifier before correcting the record.
BAD=$(sqlite3 "$DB" "SELECT body FROM guide;" | "$PY" -c '
import os, re, sys
pat = re.compile(r"(?:~|\$HOME)?/[A-Za-z0-9._/${}-]+/brain-[a-z-]+\.(?:py|sh)")
seen, bad = set(), []
for m in pat.findall(sys.stdin.read()):
    q = os.path.expanduser(os.path.expandvars(m))
    if q in seen:
        continue
    seen.add(q)
    if not os.path.isfile(q):
        bad.append(m)
print(len(seen))
for b in bad:
    print(b)
')
NPATH=$(echo "$BAD" | head -1)
for p in $(echo "$BAD" | tail -n +2); do
  fail "guide names a path that does not exist: $p (re-run brain-init.py --guide)"
done
echo "   $NPATH script path(s) named in the guide, $(( NPATH - $(echo "$BAD" | tail -n +2 | grep -c . ) )) resolve"
[ $MISS -eq 0 ] && echo "   all 7 engine scripts present"

step "8. guide is in sync with the packaged files"
DRIFT=0
for f in "$HERE"/guide/*.md; do
  t=$(basename "$f" .md)
  DBLEN=$(sqlite3 "$DB" "SELECT COALESCE(length(body),0) FROM guide WHERE topic='$t';")
  [ "${DBLEN:-0}" -eq 0 ] && { warn "guide topic $t is in guide/ but not in the db - run brain-init.py --guide"; DRIFT=1; }
done
[ $DRIFT -eq 0 ] && echo "   all $(ls "$HERE"/guide/*.md | wc -l | tr -d ' ') packaged topics are seeded"

# Problems last. The key warning here once printed before the success line and was ignored by
# its own author twice; that was not a discipline problem.
printf '\n'
if [ ${#WARNED[@]} -gt 0 ]; then
  printf 'WARNINGS (%s):\n' "${#WARNED[@]}"
  for w in "${WARNED[@]}"; do printf '  - %s\n' "$w"; done
fi
if [ ${#FAILED[@]} -gt 0 ]; then
  printf 'FAILED (%s):\n' "${#FAILED[@]}"
  for f in "${FAILED[@]}"; do printf '  - %s\n' "$f"; done
  exit 1
fi
[ ${#WARNED[@]} -eq 0 ] && echo "brain-check: all clear"
exit 0
