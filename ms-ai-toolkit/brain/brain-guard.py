#!/usr/bin/env python3
"""Session-start health canary. Silent when the brain is fine.

Why it lives here rather than in a scheduled job: anything scheduled from inside a session dies
with that session, and nothing reports the death. A session-start hook survives everything --
every new session re-arms it for free.

It must stay CHEAP and QUIET. The full brain-check.sh takes ~10s because it replays every key
through the recall hook; that is intolerable on every session start. These checks take ~30ms.
When something looks wrong it does not try to diagnose -- it says so and points at the real check.

If the brain does not exist yet it prints the one command that creates it, once, and otherwise
stays out of the way. Always exits 0: a canary must never be able to break a session start.
"""
import os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brainlib

SCRIPTS = brainlib.SCRIPTS
CHECK = f'bash "{os.path.join(SCRIPTS, "brain-check.sh")}"'


def main():
    if not os.path.exists(brainlib.DB):
        # Told once per machine. A setup nag on every session start is how a hook gets deleted.
        flag = os.path.join(brainlib.HOME, ".init-nagged")
        if os.path.exists(flag):
            return
        os.makedirs(brainlib.HOME, exist_ok=True)
        open(flag, "w").write("1")
        print("<agent-brain-guard>")
        print(f"No agent brain at {brainlib.DB}. Create it with:")
        print(f"  python3 \"{os.path.join(SCRIPTS, 'brain-init.py')}\"")
        print("</agent-brain-guard>")
        return

    problems = []
    try:
        con = sqlite3.connect(f"file:{brainlib.DB}?mode=ro", uri=True, timeout=3)
        if con.execute("PRAGMA integrity_check;").fetchone()[0] != "ok":
            problems.append("the database fails PRAGMA integrity_check")
        # Zero searchable rows on a brain that exists means the view broke, not that it is new:
        # a parser or view that silently returns nothing is indistinguishable from a system doing
        # nothing, and both render as a clean report.
        rows = con.execute("SELECT count(*) FROM search").fetchone()[0]
        if rows == 0 and con.execute("SELECT count(*) FROM fact").fetchone()[0] > 0:
            problems.append("the search view returns ZERO rows while fact has some - the view broke")
        stale = con.execute("SELECT count(*) FROM stale").fetchone()[0]
        if stale > 10:
            problems.append(f"{stale} rows need re-verification (see: SELECT * FROM stale)")
        openw = con.execute(
            "SELECT count(*) FROM work_log WHERE status='open' "
            "AND started_at < datetime('now','-14 day')").fetchone()[0]
        if openw:
            problems.append(f"{openw} work_log row(s) have been open for over 14 days - "
                            f"a stale claim makes the next agent think work is in flight")
        con.close()
    except Exception as e:
        problems.append(f"cannot read the brain: {e}")

    for f in ("brainlib.py", "brain-init.py", "brain-note.py", "brain-recall.py",
              "brain-capture.py", "brain-retrieve.py", "brain-selftest.py", "brain-check.sh"):
        if not os.path.exists(os.path.join(SCRIPTS, f)):
            problems.append(f"MISSING: {os.path.join(SCRIPTS, f)}")

    if not problems:
        return
    print("<agent-brain-guard>")
    print("The agent brain needs attention before you rely on it:")
    for p in problems:
        print(f"  - {p}")
    print(f"Run: {CHECK}   (full check, ~10s, exits non-zero on failure)")
    print("</agent-brain-guard>")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
