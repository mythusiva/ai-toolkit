#!/usr/bin/env python3
"""Write to the agent brain without the ceremony.

Why this exists: in the first 3 days every single write went to `fact`, and `code_map` gained
nothing -- even from sessions that had just spent dozens of greps locating symbols. code_map is
the table that most directly cuts the 15-call median orientation cost, and it was also the most
expensive to write by hand (needs a line number and a git blob sha). That asymmetry, not
laziness, is what shaped the corpus. So: this fills both in for you.

  brain-note.py map <repo> <path> <symbol|-> "<summary>"
  brain-note.py gotcha <scope> "<trigger>" "<symptom>" "<fix>" [cause]
  brain-note.py recipe <name> <scope> "<goal>" "<command>" [notes]
  brain-note.py fact <scope> <subject> "<claim>" "<evidence>" [tags]
  brain-note.py decision <topic> "<question>" "<chosen>" "<rejected>" "<rationale>" [who]
  brain-note.py claim <scope> "<task>" [branch]      # take work so others do not collide
  brain-note.py thread <source> <ext_id> "<title>" [url] [who]   # a stream item worth tracking
  brain-note.py verdict <thread_id> <state> "<why>"  # new|acting|declined|done
  brain-note.py done <work_log_id> [artifacts]
  brain-note.py bump <table> <id>                    # re-verified today, still true
  brain-note.py wrong <fact_id> "<what killed it>"   # disprove, never delete

Everything is parameterised, so quotes and apostrophes in the text are safe.
"""
import os, re, sqlite3, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brainlib

DB = brainlib.DB


def con():
    c = sqlite3.connect(DB, timeout=10)
    c.execute("PRAGMA busy_timeout=5000")
    return c


def anchor(repo, path, symbol):
    """git blob sha + the line the symbol is declared on, both best-effort."""
    sha = line = None
    root = brainlib.repo_path(repo)
    r = subprocess.run(["git", "-C", root or ".", "rev-parse", f"HEAD:{path}"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        sha = r.stdout.strip()[:12]
    full = os.path.join(root, path) if root else path
    if symbol and symbol != "-" and os.path.exists(full):
        sym = re.escape(symbol)
        # second pattern catches TS/JS class methods (`public async foo(`, `foo(`), which carry
        # no declaration keyword; tried only as a fallback so a call site cannot outrank a decl
        pats = [re.compile(rf"\b(class|function|const|interface|enum|type|def)\s+{sym}\b"),
                re.compile(rf"^\s*(?:(?:public|private|protected|static|readonly|abstract|async|get|set|\*)\s+)*{sym}\s*[(<]")]
        lines = open(full, errors="replace").readlines()
        for pat in pats:
            for i, ln in enumerate(lines, 1):
                if pat.search(ln):
                    line = i
                    break
            if line:
                break
    return sha, line


def sess():
    for k in ("BRAIN_SESSION_ID", "CLAUDE_SESSION_ID", "OPENCODE_SESSION_ID"):
        if os.environ.get(k):
            return os.environ[k]
    return "cli"


def require(*vals):
    """Refuse to write a row with an empty required field.

    Passing empty strings used to write a row with a blank key: unretrievable, meaningless, and
    invisible until someone audited. Fail loudly instead.
    """
    if any(v is None or not str(v).strip() for v in vals):
        print("REFUSED: a required field was empty. Nothing was written.")
        sys.exit(1)


HOOK = os.path.join(brainlib.SCRIPTS, "brain-recall.py")


def surviving_terms(key):
    """Which words of this key would actually survive the recall hook's tokenizer?

    check_key used to validate SHAPE only, so a clean-looking 3-word key like "npm ci fails"
    passed while being wholly unretrievable: npm and ci are under the length floor and fails is
    stoplisted, so ZERO terms survive. Ask the real tokenizer instead of guessing.
    """
    try:
        src = open(HOOK).read()
        stop = set(re.search(r'STOP = set\("""(.*?)"""', src, re.S).group(1).split())
        stop |= brainlib.extra_stop()
        ns = {}
        exec(re.search(r"(TOKEN_PATTERNS = \[.*?\n\])", src, re.S).group(1), {"re": re}, ns)
        out = []
        for pat, strong in ns["TOKEN_PATTERNS"]:
            for m in re.findall(pat, key):
                t = m.strip()
                floor = 3 if (strong or t.isupper()) else 4
                if len(t) >= floor and t.lower() not in stop:
                    out.append(t)
        return out
    except Exception:
        return None   # never block a write because this check itself broke


def report_key_warnings(warn, table, key):
    """Print key warnings AFTER the success line, not before it.

    They used to print first, so the last thing on screen was a cheerful "fact <- key" and the
    warning scrolled past. That happened twice in one day to the person who WROTE the warning:
    once naming a recipe brain.check (both words stoplisted) and once on an 11-word prose key.
    The last line you see should be the problem, not the success.
    """
    if not warn:
        return
    print(f"  ^^ that {table} row has a RETRIEVABILITY PROBLEM:")
    for w in warn:
        print(f"     - {w}")
    print(f"     Fix it now:  sqlite3 <db> \"UPDATE {table} SET "
          f"{'name' if table=='recipe' else 'trigger' if table=='gotcha' else 'subject'}"
          f"='<better-kebab-key>' WHERE ...\"")


def check_key(key):
    """Warn at write time if a key will be hard to retrieve.

    The agent-brain skill carries this guidance, but the skill has been invoked ZERO times while
    97 raw writes went through this script -- so the guidance has to live where the writing
    actually happens. Every rule below came from a row that turned out to be unreachable.
    """
    words = key.split()
    warn = []
    if len(words) > 5:
        warn.append(f"{len(words)}-word prose key: needs TWO distinct query terms to match "
                    f"(one is enough only if it is rare corpus-wide). Prefer kebab-case, which "
                    f"is matched per segment so every word in it becomes a search term.")
    if " " in key and re.search(r"[/.]\w", key):
        warn.append("a path or dotted name inside a prose key is INVISIBLE to plain-word search "
                    "(a word must be whitespace-delimited). Kebab the whole key instead.")
    if " " not in key and len(key) > 60:
        warn.append(f"kebab key is {len(key)} chars; segment matching only applies under 60.")
    if "/" in key and " " not in key:
        warn.append("slashes exclude a key from segment matching (paths are deliberately skipped).")
    surv = surviving_terms(key)
    if surv is not None and not surv:
        warn.append("NO WORD in this key survives the recall tokenizer (all too short or "
                    "stoplisted), so NOTHING will ever retrieve this row. Add a distinctive "
                    "term of 4+ characters, or a tool/vendor name.")
    return warn


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd, a = sys.argv[1], sys.argv[2:]
    c = con()
    try:
        if cmd == "map":
            repo, path, symbol, summary = a[0], a[1], a[2], a[3]
            require(repo, path, summary)
            if brainlib.repo_path(repo) is None:
                print(f"REFUSED: no checkout named {repo!r} found. Nothing was written. "
                      f"Set BRAIN_REPO_ROOT if your checkouts live under one root.")
                return 1
            symbol = None if symbol == "-" else symbol
            sha, line = anchor(repo, path, symbol)
            if sha is None:
                print(f"WARN: {repo}/{path} is not at HEAD (untracked or wrong path) - "
                      f"row written without an anchor, so staleness cannot be checked")
            # INSERT OR REPLACE silently destroys an existing summary. That happened during a
            # probe on 2026-08-17: re-mapping PasskeyService replaced a carefully-written summary
            # with the word "seam test", with no warning. Show what is being overwritten.
            old = c.execute("SELECT summary FROM code_map WHERE repo=? AND path=? AND "
                            "COALESCE(symbol,'')=COALESCE(?,'')", (repo, path, symbol)).fetchone()
            if old:
                print(f"  REPLACING an existing row. Previous summary was:\n    {old[0][:200]}")
                print(f"  If that was better than what you are writing, stop and merge instead.")
            c.execute("INSERT OR REPLACE INTO code_map"
                      "(repo,path,symbol,kind,summary,line,blob_sha,verified_at)"
                      " VALUES(?,?,?,?,?,?,?,date('now'))",
                      (repo, path, symbol, "file" if not symbol else "symbol",
                       summary, line, sha))
            print(f"code_map <- {repo}/{path}"
                  f"{'::'+symbol if symbol else ''} line={line} sha={sha}")
        elif cmd == "gotcha":
            require(a[0], a[1], a[2], a[3])
            _warn = check_key(a[1])
            # Same trap, hit again -> bump it, do not twin it. `hits` is the only signal for which
            # traps RECUR, and it read 1 on 276 of 279 rows because nothing ever incremented it:
            # the second encounter always arrived as a fresh INSERT under the same trigger.
            prev = c.execute("SELECT id,hits FROM gotcha WHERE scope=? AND trigger=?",
                             (a[0], a[1])).fetchone()
            if prev:
                c.execute("UPDATE gotcha SET symptom=?, fix=?, cause=COALESCE(?,cause), "
                          "hits=hits+1, verified_at=date('now') WHERE id=?",
                          (a[2], a[3], a[4] if len(a) > 4 else None, prev[0]))
                print(f"gotcha ^ {a[1][:60]}  (hit {prev[1] + 1} times - "
                      f"if it keeps biting, fix the root cause instead)")
            else:
                c.execute("INSERT INTO gotcha(scope,trigger,symptom,fix,cause) VALUES(?,?,?,?,?)",
                          (a[0], a[1], a[2], a[3], a[4] if len(a) > 4 else None))
                print("gotcha <-", a[1][:60])
            report_key_warnings(_warn, "gotcha", a[1])
        elif cmd == "recipe":
            require(a[0], a[1], a[2], a[3])
            _warn = check_key(a[0])
            c.execute("INSERT INTO recipe(name,scope,goal,command,notes,last_ok_at,ok_count)"
                      " VALUES(?,?,?,?,?,date('now'),1)",
                      (a[0], a[1], a[2], a[3], a[4] if len(a) > 4 else None))
            print("recipe <-", a[0]); report_key_warnings(_warn, "recipe", a[0])
        elif cmd == "fact":
            require(a[0], a[1], a[2], a[3])
            _warn = check_key(a[1])
            # A subject is a HANDLE, not a row id. Writing the same subject again means one of two
            # things and the old code did neither: re-verifying the same claim (refresh the date,
            # do not twin it) or correcting it (the new row supersedes the old, which is what the
            # `supersedes` column has always been for). Blind INSERT produced 5 twin subjects by
            # 2026-08-31, each one leaving the original to age into `stale` beside its own copy,
            # and both copies compete for the same recall slot.
            prev = c.execute("SELECT id,claim FROM fact WHERE scope=? AND subject=? "
                             "AND status='active' ORDER BY id DESC LIMIT 1",
                             (a[0], a[1])).fetchone()
            if prev and prev[1].strip() == a[2].strip():
                c.execute("UPDATE fact SET evidence=?, verified_at=date('now') WHERE id=?",
                          (a[3], prev[0]))
                print(f"fact = {a[1]}  (unchanged - re-verified today, no new row)")
            else:
                cur = c.execute(
                    "INSERT INTO fact(scope,subject,claim,evidence,tags,source,supersedes)"
                    " VALUES(?,?,?,?,?,?,?)",
                    (a[0], a[1], a[2], a[3], a[4] if len(a) > 4 else None, sess(),
                     prev[0] if prev else None))
                if prev:
                    c.execute("UPDATE fact SET status='superseded' WHERE id=?", (prev[0],))
                    print(f"fact <- {a[1]}  (#{cur.lastrowid} supersedes #{prev[0]}, which said:"
                          f"\n    {prev[1][:160]})")
                else:
                    print("fact <-", a[1])
            report_key_warnings(_warn, "fact", a[1])
        elif cmd == "decision":
            c.execute("INSERT INTO decision(topic,question,chosen,rejected,rationale,decided_by)"
                      " VALUES(?,?,?,?,?,?)",
                      (a[0], a[1], a[2], a[3], a[4], a[5] if len(a) > 5 else "agent"))
            print("decision <-", a[0])
        elif cmd == "claim":
            open_rows = c.execute(
                "SELECT id,session,task FROM work_log WHERE scope=? AND status='open'",
                (a[0],)).fetchall()
            for r in open_rows:
                print(f"NOTE: work_log #{r[0]} already open in {a[0]} by {r[1][:8]}: {r[2][:70]}")
            cur = c.execute("INSERT INTO work_log(session,scope,task,branch) VALUES(?,?,?,?)",
                            (sess(), a[0], a[1], a[2] if len(a) > 2 else None))
            print(f"work_log #{cur.lastrowid} claimed - close it with: brain-note.py done {cur.lastrowid}")
        elif cmd == "thread":
            # Stream state, not knowledge: an item seen in slack/github/jira/datadog that may or
            # may not deserve action. Deliberately absent from the `search` view, so it never
            # joins the recall surface loaded into every session.
            require(a[0], a[1], a[2])
            cur = c.execute(
                "INSERT INTO thread(source,external_id,title,url,who) VALUES(?,?,?,?,?)"
                " ON CONFLICT(source,external_id) DO UPDATE SET last_seen=datetime('now')",
                (a[0], a[1], a[2], a[3] if len(a) > 3 else None, a[4] if len(a) > 4 else None))
            print(f"thread <- {a[0]}/{a[1]} #{cur.lastrowid}"
                  f" - record the outcome with: brain-note.py verdict {cur.lastrowid} declined \"<why>\"")
        elif cmd == "verdict":
            # The `declined` state is the only thing in this database that no upstream system
            # holds: Slack, GitHub and Jira all record what happened, never what was considered
            # and consciously left alone.
            states = ("new", "acting", "declined", "done")
            if len(a) < 3 or a[1] not in states:
                print(f"usage: brain-note.py verdict <thread_id> <{'|'.join(states)}> \"<why>\"")
                return 1
            # Same doctrine as done/bump/wrong above: an UPDATE matching nothing must not report
            # success, or an agent believes a decision was recorded that was never stored.
            cur = c.execute("UPDATE thread SET state=?,verdict=?,last_seen=datetime('now')"
                            " WHERE id=?", (a[1], a[2], int(a[0])))
            if cur.rowcount == 0:
                print(f"NO SUCH thread ROW: #{a[0]}. Nothing changed. List them with: "
                      f"sqlite3 {DB} \"SELECT id,source,title,state FROM thread WHERE state IN ('new','acting');\"")
                return 1
            print(f"thread #{a[0]} -> {a[1]}: {a[2][:70]}")
        elif cmd == "done":
            # Same class as bump/wrong: an UPDATE matching nothing must not report success.
            # A stale open work_log row is worse than none, because it makes the next agent
            # believe work is in flight -- so "closed" has to mean closed.
            cur = c.execute("UPDATE work_log SET status='done',updated_at=datetime('now'),"
                            "artifacts=COALESCE(?,artifacts) WHERE id=? AND status<>'done'",
                            (a[1] if len(a) > 1 else None, int(a[0])))
            if cur.rowcount == 0:
                exists = c.execute("SELECT status FROM work_log WHERE id=?",
                                   (int(a[0]),)).fetchone()
                if exists:
                    print(f"work_log #{a[0]} was ALREADY {exists[0]}. Nothing changed.")
                else:
                    print(f"NO SUCH work_log ROW: #{a[0]}. Nothing was closed. "
                          f"List open work with: SELECT id,scope,task FROM work_log "
                          f"WHERE status='open';")
                return 1
            print("work_log closed:", a[0])
        elif cmd == "bump":
            col = "last_ok_at" if a[0] == "recipe" else "verified_at"
            cur = c.execute(f"UPDATE {a[0]} SET {col}=date('now') WHERE id=?", (int(a[1]),))
            if cur.rowcount == 0:
                print(f"NO SUCH ROW: {a[0]} #{a[1]} does not exist. Nothing was changed.")
                return 1
            print(f"{a[0]} #{a[1]} re-verified today")
        elif cmd == "wrong":
            fid = int(a[0])
            # Reporting success on a no-op UPDATE is the worst failure this script can have: an
            # agent believes it retired a wrong fact, and the wrong fact stays active.
            cur = c.execute("UPDATE fact SET status='disproven',"
                            "evidence=evidence||' | DISPROVEN '||date('now')||': '||? WHERE id=?",
                            (a[1], fid))
            if cur.rowcount == 0:
                print(f"NO SUCH FACT: #{fid} does not exist. NOTHING was disproven - "
                      f"find the right id with: SELECT id,subject FROM fact WHERE subject LIKE ...")
                return 1
            print(f"fact #{fid} marked disproven - now insert the replacement with "
                  f"supersedes={fid} so the dead end stays recorded")
        else:
            print(__doc__)
            return 1
        c.commit()
    except IndexError:
        print("missing argument.\n" + __doc__)
        return 1
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
