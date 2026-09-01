#!/usr/bin/env python3
"""Can each row in the brain be retrieved by typing its own key?

This is the measurement that found two silent recall defects. The signal is the RATIO, not the
absolute count: a session added 10 rows and unreachable went 5/311 -> 8/321, i.e. 3 of 10 NEW
rows were unfindable (30%) against a 1.6% baseline. Watch the ratio on new rows.

A row that cannot be retrieved by its own exact key cannot be retrieved by anything, so this is
the weakest possible bar and still catches real breakage -- stoplist over-reach, and a per-term
fetch cap set below the broad-term threshold that discarded rows the broad filter had accepted.

  brain-retrieve.py              # ratio + the unreachable keys
  brain-retrieve.py --quiet      # just the ratio line, for brain-check.sh
  brain-retrieve.py --new 30     # only rows verified in the last 30 days
"""
import contextlib, importlib.util, io, json, os, sqlite3, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import brainlib


def load_recall():
    """Import the hook as a module so every probe reuses one process. Per-row subprocesses cost
    ~50ms each, which turns a 500-row corpus into half a minute nobody will wait for."""
    spec = importlib.util.spec_from_file_location("brain_recall",
                                                 os.path.join(HERE, "brain-recall.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def probe(recall, key, session, cwd):
    """Feed `key` in as a prompt and return the hook's output."""
    payload = json.dumps({"prompt": key, "session_id": session, "cwd": cwd})
    out = io.StringIO()
    stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(payload)
        with contextlib.redirect_stdout(out):
            recall.main()
    except Exception:
        pass
    finally:
        sys.stdin = stdin
    return out.getvalue()


def main():
    quiet = "--quiet" in sys.argv
    days = None
    if "--new" in sys.argv:
        days = int(sys.argv[sys.argv.index("--new") + 1])

    if not os.path.exists(brainlib.DB):
        print(f"no brain at {brainlib.DB} - run brain-init.py")
        return 1
    con = sqlite3.connect(f"file:{brainlib.DB}?mode=ro", uri=True)
    q = "SELECT kind,key,verified_at FROM search"
    if days:
        q += f" WHERE verified_at >= date('now','-{days} day')"
    rows = con.execute(q).fetchall()
    con.close()
    if not rows:
        print("0 rows to check")
        return 0

    # A throwaway state dir: the delivered log would otherwise suppress the second probe of any
    # row, and a measurement run must not write into the state the real hooks read.
    tmp = tempfile.mkdtemp(prefix="brain-retrieve-")
    os.environ["BRAIN_DELIVERED_DIR"] = os.path.join(tmp, "delivered.d")
    recall = load_recall()

    unreachable = []
    for i, (kind, key, ver) in enumerate(rows):
        out = probe(recall, key, f"retrieve-probe-{i}", os.getcwd())
        # The key is echoed verbatim in the injected line, so a plain containment test is exact.
        if key not in out:
            unreachable.append((kind, key, ver))

    n, u = len(rows), len(unreachable)
    pct = 100.0 * u / n
    scope = f"rows verified in the last {days}d" if days else "all rows"
    print(f"retrievable: {n - u}/{n} ({100 - pct:.1f}%) - {u} unreachable, {scope}")
    if not quiet and unreachable:
        print("\nUnreachable by their own key -- rekey these (see guide topic 09_lessons):")
        for kind, key, ver in unreachable[:40]:
            print(f"  [{kind}] {key}   (verified {ver})")
        if u > 40:
            print(f"  ... and {u - 40} more")
    # Non-zero only on a ratio that is clearly broken, not on one bad row: the baseline measured
    # on a healthy corpus was 1.2-1.6% unreachable, and a key or two always needs rework.
    return 1 if pct > 10 else 0


if __name__ == "__main__":
    sys.exit(main())
