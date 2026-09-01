#!/usr/bin/env python3
"""Recall hook: query the agent brain for terms in the prompt and inject any hits.

Wired to UserPromptSubmit in Claude Code and to "chat.message" in opencode; both hand it
{prompt, session_id, cwd} on stdin and put whatever it prints in front of the model.

Deterministic recall. A skill would only fire when the model already suspects the DB has
something, which is exactly the judgement it cannot make at turn 1 -- the failure mode is not
knowing that you do not know. So this runs unconditionally and decides by data, not by model.

Silent on zero hits, always exit 0. The critic-panel Stop hook was deleted on 2026-08-05 after
firing 687 times; an always-on hook that adds noise gets retired, so this one costs nothing
when it has nothing to say.
"""
import datetime, hashlib, json, os, re, sqlite3, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brainlib

DB = brainlib.DB
MAX_ROWS = 8
MAX_BODY = 240
MIN_TERM = 4
# A term matching more than this FRACTION of the corpus is noise, not signal. It must be a
# fraction, not a fixed count: an absolute 8 was right at 114 rows, but by 150 it was suppressing
# real domain terms (passkey 13, transactions 13, datadog 17) and the corpus keeps growing.
# Measured on 1164 real prompts: proportional costs +2.6% injected rows over the absolute 8.
BROAD_FRAC = float(os.environ.get("BRAIN_BROAD_FRAC", "0.08"))
BROAD_MIN = 8      # floor, so a small corpus does not treat everything as broad
# A word this user types in more than this share of their own prompts is a FUNCTION word for
# them, whatever a dictionary says. Measured over 910 distinct prompts on 2026-08-31:
# review 10.9%, https 10.5%, service 10.2%, already 9.2%, existing 8.6%, pull 6.9% -- against
# portal 4.9%, repo 3.7%, passkey 3.0%, kafka 0.5%. Those five were the single largest class of
# false positives (323 of 934 unique injected rows over 50 sessions). Cut at 6%: it clears
# `portal` and `repo`, which are real domain terms here, with room on both sides.
# `term_df` is rebuilt by brain-df.py; if it is missing the rule is simply inert.
COMMON_DF = float(os.environ.get("BRAIN_COMMON_DF", "0.06"))
# Where each session records what it has already been handed. Doubles as the delivery log that
# brain-precision.py scores -- one file, two jobs, and nothing writes to the DB on the hot path.
DELIVERED_DIR = os.environ.get("BRAIN_DELIVERED_DIR", os.path.join(brainlib.HOME, "delivered.d"))

# Words that would match half the corpus and drown the real signal.
STOP = set("""
about
above
add
adding
after
again
against
agent
agents
all
along
also
always
and
another
answer
answers
anybody
anyone
anything
anywhere
any
are
around
because
been
before
being
between
bit
both
brain
branch
build
builds
but
can
cant
case
cases
change
changed
changes
changing
check
claude
clear
close
code
come
copy
could
create
creates
data
delete
deletes
dev
did
does
doing
done
dont
down
during
each
else
enough
error
errors
even
ever
every
everybody
everyone
everything
everywhere
fail
failed
failing
fails
feature
features
few
file
files
find
finds
fine
first
fix
for
format
from
fullstack
further
get
gets
give
goes
going
good
got
guide
guides
had
has
have
having
help
here
how
however
into
issue
issues
its
itself
just
keep
know
let
like
line
lines
list
lists
look
looked
looks
lot
made
main
make
many
may
might
more
most
move
much
must
name
names
need
never
new
next
nice
not
nothing
now
off
okay
old
once
only
onto
open
other
our
out
output
outputs
over
own
plan
plans
please
point
points
print
problem
problems
put
ran
read
reads
ready
reason
reasons
remove
repos
result
results
run
running
same
say
screenshot
screenshots
see
session
sessions
should
show
shows
since
some
somebody
someone
something
somewhere
start
starting
still
stop
stuff
such
sure
take
tell
test
testing
tests
than
thanks
that
the
their
them
then
there
these
they
thing
things
this
those
through
time
too
under
until
update
updates
upon
use
used
user
users
using
value
values
very
want
was
way
ways
well
were
what
when
where
whether
which
while
who
why
will
with
within
without
work
working
works
would
write
writes
yeah
yes
you
your
yours
""".split()) | brainlib.extra_stop()

# strong = the user is naming a specific thing, so an incidental mention inside another row's
# body is still a real lead. weak = ordinary English, which lands in body text by coincidence
# ("write me a haiku" matching a row that happens to say "writes the cache entry"), so a weak
# term only counts when it matches a row's KEY -- i.e. that row is actually about it.
TOKEN_PATTERNS = [
    (r"`([^`]{3,60})`", True),                         # backticked -- named exactly
    (r"\b([A-Za-z]+[a-z]+[A-Z][A-Za-z0-9]+)\b", True), # CamelCase / camelCase identifiers
    (r"\b([a-zA-Z][a-zA-Z0-9]*_[a-zA-Z0-9_]+)\b", True),  # snake_case
    (r"\b([\w.-]+\.(?:ts|tsx|js|jsx|py|sql|md|json|yml|yaml|sh|kt|swift|db))\b", True),
    # ALL-CAPS words are NOT distinctive enough to match body text: DIFF, CRITIC and OMEGA
    # each pulled unrelated rows on ~9% of 1161 replayed historical prompts. Key-only.
    (r"\b([A-Z]{3,})\b", False),                       # ACRONYMS / ENV_VARS
    (r"\b(\d+(?:px|rem|em|xl|kb|mb|gb|ms|s))\b", True),  # design tokens / units: 16px, 2xl, 500ms
    (r"\b([A-Z]{2,}-?\d{3,})\b", True),                # error/ticket codes: TS2584, OMEGA-9945
    (r"(\.[a-z]+(?:\.[a-z]+)+)\b", True),               # dotfiles: .env.local, .env.develop
    # Case-INsensitive on purpose. This was [a-z]{4,} until 2026-08-17, which made any capitalised
    # ordinary word invisible: "Aikido is red" found nothing while "aikido is red" worked, and a
    # sentence-initial capital is the single most common shape in a real prompt. Strong patterns
    # run first and `seen` dedupes, so nothing is double-counted.
    (r"\b([A-Za-z]{4,})\b", False),                    # plain words ("lint", "jest", "Aikido")
]


_REPO_SCOPE = {}


def is_repo_scope(scope):
    """Is this scope the name of a checkout, rather than a topic?

    Scopes are a mix of repo names (portal, user-service) and topic slugs (global, passkeys,
    chrome, orchestration). Only the first kind says WHERE something lives, which is the only kind
    a cross-repo test can reason about.
    """
    if not scope:
        return False
    if scope not in _REPO_SCOPE:
        _REPO_SCOPE[scope] = brainlib.repo_path(scope) is not None
    return _REPO_SCOPE[scope]


def whole_word(term, text):
    """Weak terms must match a key as a FREE-STANDING word.

    Not a substring: otherwise "service" in an ordinary sentence pulls back TwilioService,
    PasskeyService and UserWorkspaceService. And not a segment of a compound identifier
    either -- "baselane" inside the key "baselane-fullstack/scripts/start-mobile-ios.sh" is
    delimited by a hyphen, and matched 3 real prompts about presentations in the first 3 days
    because every path on this machine contains it. So the delimiter must be whitespace or a
    string edge, never punctuation internal to a path or identifier.
    """
    text = text or ""
    if re.search(rf"(?:^|\s)[\"\'`(\[]?{re.escape(term)}[\"\'`)\],.:;!?]?(?:\s|$)",
                 text, re.I):
        return True
    # A SHORT identifier key is a deliberate name, not prose: ios.simulator-drive should be
    # findable by "simulator". Long path-like keys are not eligible -- that is exactly how
    # "baselane" inside baselane-fullstack/scripts/... became a false positive.
    # A space-free key is a deliberate identifier (ispublic-decorator-is-decorative,
    # ios.simulator-drive) and every segment of it is a real search term. Keys containing a
    # slash are PATHS and stay excluded -- that is what made "baselane" inside
    # baselane-fullstack/scripts/start-mobile-ios.sh a false positive on 3 unrelated prompts.
    if " " not in text and "/" not in text and len(text) <= 60:
        return term.lower() in [seg.lower() for seg in re.split(r"[.\-_]", text)]
    return False


def drifted_paths(rows):
    """Which of these code_map rows no longer match the file at HEAD?

    Verification happens at the moment of USE, not on a timer: a 30-day window says nothing
    about a file edited yesterday, and a row that is confidently wrong costs more than an
    absent one. One `git ls-tree` per repo covers every path in that repo at once.
    """
    by_repo = {}
    for repo, path, sha in rows:
        if repo and path and sha:
            by_repo.setdefault(repo, []).append((path, sha))
    drifted = set()
    for repo, items in by_repo.items():
        root = brainlib.repo_path(repo)
        if root is None:
            # A row pointing at a repo that no longer exists is definitively wrong, not unknown.
            # This used to `continue`, so a deleted or renamed repo read as CURRENT -- the row was
            # handed over unflagged. Silence about a missing repo is worse than silence about a
            # changed file, because nothing about that row can still be true.
            for p, _ in items:
                drifted.add((repo, p))
            continue
        try:
            out = subprocess.run(
                ["git", "-C", root, "ls-tree", "HEAD", "--"] + [p for p, _ in items],
                capture_output=True, text=True, timeout=3,
            ).stdout
        except Exception:
            continue  # never let verification failure suppress the recall itself
        head = {}
        for line in out.splitlines():
            meta, _, p = line.partition("\t")
            parts = meta.split()
            if len(parts) >= 3:
                head[p.strip('"')] = parts[2]
        for p, sha in items:
            cur = head.get(p)
            if cur is None or not cur.startswith(sha):
                drifted.add((repo, p))
    return drifted


URL = re.compile(r"\bhttps?://[^\s<>()\"\']+")


def url_terms(prompt):
    """Pull the identifiers out of a pasted URL, then take the URL out of the prompt.

    A URL word-splits into `https`, `github`, `pull` -- all three ordinary words that match rows
    about GitHub tooling, none of them what the question is about. Measured 2026-08-31: the prompt
    "this is actually break existing logins right? <a user-service PR link>" spent 4 of its 8 slots
    on GitHub CLI rows, while the one token in the URL that mattered -- user-service -- was split
    on its hyphen into two stopwords. So: harvest the segments that are IDENTIFIERS (hyphenated,
    underscored, or a 3+ digit id) as strong terms, and discard the rest of the URL entirely.
    """
    out = []
    for u in URL.findall(prompt):
        for seg in re.split(r"[/?&=#:]+", u):
            seg = seg.strip(".")
            if re.fullmatch(r"\d{3,}", seg) or (len(seg) >= 4 and re.search(r"[-_]", seg)
                                                and "." not in seg):
                out.append(seg)
    return out, URL.sub(" ", prompt)


def terms_from(prompt):
    seen, out = set(), []
    url_first, prompt = url_terms(prompt)
    for t in url_first:
        if t.lower() not in seen:
            seen.add(t.lower())
            out.append((t, True))
    for pat, strong in TOKEN_PATTERNS:
        for m in re.findall(pat, prompt):
            t = m.strip()
            # Strong tokens may be 3 chars: OTP, API, JWT, SSM, AWS, DNS and FK are core
            # vocabulary here and were ALL invisible under a flat 4-char floor. Weak words keep
            # the higher floor, since 3-letter English words carry no signal.
            # ALL-CAPS tokens are weak (key-only) so DIFF/CRITIC cannot pull body matches, but
            # they still need the 3-char floor: OTP, API, JWT, SSM, AWS, DNS are core vocabulary
            # and were invisible under a flat 4-char floor.
            floor = 3 if (strong or t.isupper()) else MIN_TERM
            if len(t) < floor or t.lower() in STOP or t.lower() in seen:
                continue
            seen.add(t.lower())
            out.append((t, strong))
    return out[:25]



def prune_markers(d, keep=400):
    """Keep the marker directory bounded. One file per session, forever, is an unbounded
    accumulator -- roughly 3,650 files a year at ten sessions a day. Nothing breaks at that
    size, which is exactly why it would never get noticed."""
    try:
        fs = [os.path.join(d, x) for x in os.listdir(d)]
        if len(fs) <= keep:
            return
        fs.sort(key=os.path.getmtime)
        for old in fs[:-keep]:
            os.remove(old)
    except Exception:
        pass

def delivered_path(session):
    return os.path.join(DELIVERED_DIR, f"{session}.jsonl") if session else None


def load_delivered(session):
    """What this session has already been handed.

    A row the session received on prompt 3 is still in its context on prompt 20; sending it again
    buys nothing and costs a slot that a NEW row could have used. Measured over 50 sessions on
    2026-08-31: 1,161 of 2,095 delivered rows (56% of all injected bytes, ~100k tokens) were a
    repeat within the same session, and two /loop monitors accounted for most of it -- one
    delivered 667 rows of which 73 were distinct. The dedupe happens AFTER ranking, so a freed
    slot is filled by the next-best row rather than left empty.
    """
    f = delivered_path(session)
    if not f or not os.path.exists(f):
        return set()
    out = set()
    try:
        for line in open(f, errors="replace"):
            try:
                d = json.loads(line)
            except Exception:
                continue
            out.add(f"{d.get('kind')}:{d.get('id')}")
    except Exception:
        pass
    return out


def record_delivered(session, prompt, rows):
    """Append what we just handed over. This file IS the delivery log.

    Nothing anywhere recorded whether a delivered row was ever used, which is why five separate
    defects went unmeasured for two weeks. Written as a spool rather than straight into the DB so
    the hot path never takes a write lock -- brain-precision.py folds it in later.
    """
    f = delivered_path(session)
    if not f:
        return
    try:
        os.makedirs(DELIVERED_DIR, exist_ok=True)
        ph = hashlib.md5(prompt[:300].encode()).hexdigest()[:12]
        with open(f, "a") as fh:
            for rank, (kind, key, _b, _v, term, rid, _rare, scope_hit) in enumerate(rows, 1):
                fh.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"),
                                     "kind": kind, "id": rid, "key": key, "terms": term,
                                     "rank": rank, "scope_hit": bool(scope_hit),
                                     "prompt": ph}) + "\n")
        prune_markers(DELIVERED_DIR)
    except Exception:
        pass


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    prompt = payload.get("prompt") or ""
    if not prompt.strip() or not os.path.exists(DB):
        return

    # Machine-generated prompts are not questions. Stop-hook feedback, loop wakeups and the
    # brain's own monitoring prompts all arrive as user messages, and injecting into them spends
    # tokens on nobody's question -- a precision sample showed them producing pure coincidence
    # matches ('loop', 'gate', 'scoped'). They were already excluded from the metrics; exclude
    # them from the work too.
    # <task-notification> was missing until 2026-08-31 and cost 303 rows (14% of everything
    # delivered over 50 sessions): a background task finishing mid-session drew a full 8-row
    # injection matched on whatever words happened to be in the notification envelope.
    MACHINE = ("Stop hook feedback:", "Continue monitoring agent-brain.db until",
               "[2 prior /loop wakeups", "<command-name>", "Caveat:",
               "<task-notification>", "<system-reminder>", "<local-command")
    lead = prompt.lstrip()
    if any(lead.startswith(m) for m in MACHINE) or lead.startswith("[") and "/loop" in lead[:60]:
        return

    # scope = the repo directory under ~/baselane that this session is working in
    session = payload.get("session_id") or ""
    cwd = payload.get("cwd") or os.getcwd()
    repo = brainlib.scope_for(cwd)

    already = load_delivered(session)

    terms = terms_from(prompt)
    if not terms:
        return

    try:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=2)
    except Exception:
        return

    corpus = con.execute("SELECT count(*) FROM search").fetchone()[0] or 1
    broad = max(BROAD_MIN, int(corpus * BROAD_FRAC))
    # How often this user types each of these words. Missing table or missing term = rare, so a
    # brain without term_df behaves exactly as it did before this rule existed.
    df, df_n = {}, 0
    try:
        df_n = int(con.execute(
            "SELECT value FROM meta WHERE key='term_df_prompts'").fetchone()[0])
        q = ",".join("?" * len(terms))
        df = {t.lower(): c for t, c in con.execute(
            f"SELECT term,prompts FROM term_df WHERE term IN ({q})",
            [t.lower() for t, _ in terms])}
    except Exception:
        df, df_n = {}, 0
    common_cut = df_n * COMMON_DF if df_n else 10 ** 9
    hits, cand, rarity = [], {}, {}
    try:
        for t, strong in terms:
            like = f"%{t}%"
            where = "key LIKE ? OR body LIKE ?" if strong else "key LIKE ?"
            args = (like, like) if strong else (like,)
            # A term matching a large share of the corpus ("service", "error") carries no
            # signal and would crowd out the specific hits. Let the data decide rather than
            # maintaining a stopword list that rots as the corpus grows.
            n = con.execute(f"SELECT count(*) FROM search WHERE {where}", args).fetchone()[0]
            if n == 0 or n > broad:
                continue
            rarity[t] = n
            # Exact-ish key matches rank above incidental body mentions.
            rows = con.execute(
                "SELECT kind,key,body,verified_at,id,scope,"
                "  (CASE WHEN key LIKE ? THEN 0 ELSE 1 END) AS rank "
                f"FROM search WHERE {where} "
                "ORDER BY rank, verified_at DESC LIMIT ?",
                # Fetch EVERY match for this term. The old cap was PER_TERM*4 = 8, which
                # truncated before multi-term scoring ran, so a row matching two terms could be
                # dropped for not being in either term's top 8 -- measured 2026-08-19:
                # portal.start-local matches both 'portal' (10 keys) and 'local' (21 keys) and
                # was unreachable even by its own exact key. `n` is already bounded: any term
                # matching more than `broad` rows was skipped above, so this cannot blow up.
                (like,) + args + (n,),
            ).fetchall()
            for kind, key, body, ver, rid, scope, _ in rows:
                sig = (kind, key)
                if not strong and not whole_word(t, key):
                    continue
                cand.setdefault(sig, {"row": (kind, key, body, ver, rid, scope),
                                      "terms": set(), "strong": False})
                cand[sig]["terms"].add(t)
                cand[sig]["strong"] |= strong

        # A sentence-shaped key ("Starting a backend service against the local stack") will
        # match any common word in it, so one weak term is not evidence that the row is about
        # what was asked. Demand two distinct terms before trusting a long key. Identifier-like
        # keys (AppLogger, npm run lint) stay on a single term.
        for sig, v in cand.items():
            kind, key, body, ver, rid, scope = v["row"]
            rarest = min(rarity.get(t, 99) for t in v["terms"])
            # ...unless one of the matching terms is rare corpus-wide ("aikido" hits exactly one
            # row): a term that discriminates on its own does not need a second one to vouch.
            if len(key.split()) > 5 and len(v["terms"]) < 2 and rarest > 2:
                continue
            # Does this row belong to the repo the session is working in? That is the only
            # corroboration available when the question is asked in ordinary words, and it is
            # what separates a real lone-word hit from a coincidence: "where can i watch the
            # consume rate for user-service" should reach kafka-consume-floor (scope
            # user-service) and must not reach local-tts-rate (scope global).
            scope_hit = bool(repo) and (scope or "").lower() == repo.lower()
            # Every matching term is a word this user types constantly -> the match is about
            # English, not about the row. 'already', 'existing', 'review', 'https', 'pull'.
            if all(df.get(t.lower(), 0) >= common_cut for t in v["terms"]):
                continue
            # A lone ORDINARY word pointing at a DIFFERENT repo than the one you are standing in
            # is not evidence. "are those already preset?" asked in partner-embed-harness matched
            # portal-jest-eslint-NODE_ENV-local-babel-preset-react-app on the single word 'preset'.
            # Identifier matches are exempt -- naming a thing exactly is itself the evidence -- and
            # so are non-repo scopes ('global', 'passkeys', 'chrome'), which are topics, not places.
            #
            # Corpus rarity was tried here first and REJECTED on 2026-08-31: it does not separate
            # the classes at any threshold. The good lone-word hits sit at 5-9 matching rows
            # (aikido 5, search 6, owner 7, lint 9) and the bad ones straddle them (preset 2,
            # rate 13). Cutting at 3 cost five must-hit cases and still let 'preset' through.
            if (not v["strong"] and len(v["terms"]) < 2 and repo
                    and not scope_hit and is_repo_scope(scope)):
                continue
            hits.append((kind, key, (body or "")[:MAX_BODY], ver,
                         "+".join(sorted(v["terms"])[:3]), rid, rarest, scope_hit))
        # Rank by most matching terms, then by the RAREST matching term: "phone" matching 4 rows
        # is far more discriminating than "passkey" matching 19. A cold-start probe showed two
        # generic passkey rows outranking the exact phone row on a question about phone numbers.
        # A scope match counts as one extra term: being about the repo you are standing in is
        # worth as much as a second word, and no more.
        hits.sort(key=lambda h: (-(len(h[4].split("+")) + (1 if h[7] else 0)), h[6]))
        hits = [h for h in hits if f"{h[0]}:{h[5]}" not in already][:MAX_ROWS]

        # Verify the code rows we are about to hand over, before we hand them over.
        cm_ids = [h[5] for h in hits[:MAX_ROWS] if h[0] == "code_map"]
        anchors = {}
        if cm_ids:
            q = ",".join("?" * len(cm_ids))
            anchors = {
                rid: (repo_, path_, sha_)
                for rid, repo_, path_, sha_ in con.execute(
                    f"SELECT id,repo,path,blob_sha FROM code_map WHERE id IN ({q})", cm_ids
                )
            }

        # Collisions matter even when nothing else matched: another agent may hold this work.
        # But only surface rows that could actually collide with THIS session -- same repo,
        # different session. An unconditional list turns into wallpaper within a day, and a
        # hook that prints wallpaper gets deleted.
        # ONCE PER SESSION. A long-running claim otherwise warns on every single prompt in that
        # repo: a 6-day monitoring claim fired 17 times in one day, on prompts as unrelated as
        # "add a healthcheck to the compose spec", and it turned prompts that would have been
        # silent into noisy ones. You need to know about a collision once, not continuously.
        open_work = []
        if repo and session:
            seen_dir = os.path.join(brainlib.HOME, "collide.d")
            marker = os.path.join(seen_dir, f"{session}-{repo}")
            if not os.path.exists(marker):
                open_work = con.execute(
                    "SELECT scope,branch,task,status FROM work_log "
                    "WHERE status IN ('open','blocked') AND scope = ? AND session <> ? "
                    "ORDER BY updated_at DESC LIMIT 5",
                    (repo, session),
                ).fetchall()
                if open_work:
                    try:
                        os.makedirs(seen_dir, exist_ok=True)
                        open(marker, "w").write("1")
                        prune_markers(seen_dir)
                    except Exception:
                        pass
    except Exception:
        return
    finally:
        con.close()

    if not hits and not open_work:
        return

    print("<agent-brain-recall>")
    print("Prior verified knowledge from the agent brain. Trust it over your priors, but "
          "re-verify any code_map row whose blob_sha no longer matches HEAD.")
    drift = drifted_paths([anchors[i] for i in anchors])
    for kind, key, body, ver, term, rid, _rare, _scope_hit in hits[:MAX_ROWS]:
        flag = ""
        a = anchors.get(rid)
        if a and (a[0], a[1]) in drift:
            flag = " [STALE: file changed since this was verified -- re-read it and update the row]"
        print(f"- [{kind}] {key} (matched '{term}', verified {ver}){flag}: {body}")
    if open_work:
        print("Open work claimed by other agents:")
        for scope, branch, task, status in open_work:
            print(f"- [{status}] {scope} {branch or ''} :: {task}")
    print("</agent-brain-recall>")
    record_delivered(session, prompt, hits[:MAX_ROWS])


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # a recall hook must never be able to break a turn
