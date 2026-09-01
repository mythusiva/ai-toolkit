#!/usr/bin/env python3
"""End-to-end seam probe. Pushes real values through init -> write -> recall -> capture.

Corpus-independent by construction: it builds its own throwaway brain in a temp dir, so it
proves the MECHANISM on a fresh install rather than asserting that particular rows exist. That
distinction matters -- the suite this replaces asserted specific keys and would fail on day one
of any new install.

Why it is shaped as a seam probe and not unit tests: components correct against their own spec
were still wrong together. A recall injection faked a write and silenced the capture nudge; a key
validator checked shape while the read path could not retrieve the key. Neither has a unit test
that fails. Both are caught by running one value all the way through.

  python3 brain-selftest.py          # quiet unless something fails
  python3 brain-selftest.py -v       # print every case
"""
import json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VERBOSE = "-v" in sys.argv
FAILED = []
PASSED = [0]


def check(name, cond, detail=""):
    if cond:
        PASSED[0] += 1
        if VERBOSE:
            print(f"  ok   {name}")
    else:
        FAILED.append(f"{name}{': ' + detail if detail else ''}")
        print(f"  FAIL {name}" + (f"\n       {detail}" if detail else ""))


def run(script, args=(), stdin="", env=None):
    e = dict(os.environ)
    e.update(env or {})
    p = subprocess.run([sys.executable, os.path.join(HERE, script), *args],
                       input=stdin, capture_output=True, text=True, env=e)
    return p.returncode, p.stdout, p.stderr


def claude_transcript(path, tools):
    """A Claude Code transcript is JSONL with tool_use/tool_result inside message.content[]."""
    with open(path, "w") as fh:
        for name, inp, err in tools:
            content = [{"type": "tool_use", "name": name, "input": inp}]
            if err:
                content.append({"type": "tool_result", "is_error": True})
            fh.write(json.dumps({"message": {"content": content}}) + "\n")


def opencode_messages(tools):
    """The same session as opencode sees it: parts of type 'tool', lower-case names, and the
    failure carried on the part's own state rather than a separate result entry."""
    lower = {"Bash": "bash", "Read": "read", "Grep": "grep", "Edit": "edit",
             "Write": "write", "Agent": "task", "Glob": "glob"}
    parts = []
    for name, inp, err in tools:
        parts.append({"type": "tool", "tool": lower.get(name, name.lower()),
                      "state": {"status": "error" if err else "completed", "input": inp}})
    return [{"info": {"role": "assistant"}, "parts": parts}]


def main():
    tmp = tempfile.mkdtemp(prefix="brain-selftest-")
    home = os.path.join(tmp, "state")
    db = os.path.join(tmp, "brain.db")
    repo = os.path.join(tmp, "checkouts", "widget-service")
    os.makedirs(repo)
    ENV = {"BRAIN_HOME": home, "BRAIN_DB": db,
           "BRAIN_REPO_ROOT": os.path.join(tmp, "checkouts"),
           "BRAIN_STOP_EXTRA": "acmecorp"}
    try:
        print("brain-selftest")

        # --- 1. init -------------------------------------------------------------------
        rc, out, err = run("brain-init.py", env=ENV)
        check("init exits 0", rc == 0, err.strip()[:300])
        check("init reports integrity ok", "integrity_check: ok" in out, out.strip()[:200])
        check("init seeds the guide", "guide topics seeded: 7" in out, out.strip()[:200])
        check("init is idempotent", run("brain-init.py", env=ENV)[0] == 0)

        import sqlite3
        con = sqlite3.connect(db)
        topics = [r[0] for r in con.execute("SELECT topic FROM guide ORDER BY topic")]
        check("guide has the lessons topic", "09_lessons" in topics, str(topics))
        body = con.execute("SELECT body FROM guide WHERE topic='00_read_me_first'").fetchone()[0]
        check("guide placeholders resolved", "@DB@" not in body and db in body,
              "a guide the agent reads must never name a path that does not exist")

        # --- 2. write ------------------------------------------------------------------
        # A real tracked file, so the map row can take a genuine blob sha.
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
        os.makedirs(os.path.join(repo, "src"))
        open(os.path.join(repo, "src", "throttle.ts"), "w").write(
            "export class OtpThrottle {\n  check() {}\n}\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)

        rc, out, err = run("brain-note.py", ["map", "widget-service", "src/throttle.ts",
                                             "OtpThrottle", "throttles otp sends per msisdn"],
                           env=ENV)
        check("note map exits 0", rc == 0, (out + err).strip()[:300])
        row = con.execute("SELECT repo,path,symbol,line,blob_sha FROM code_map").fetchone()
        check("map row landed", row is not None and row[2] == "OtpThrottle", str(row))
        check("map row got its line number", row and row[3] == 1, str(row))
        check("map row got a blob sha", row and row[4] and len(row[4]) == 12, str(row))

        rc, out, err = run("brain-note.py",
                           ["fact", "widget-service", "kafka-retry-topic-is-per-consumer",
                            "each consumer group gets its own retry topic",
                            "src/kafka/retry.ts:44 plus the topic list in the broker"], env=ENV)
        check("note fact exits 0", rc == 0, (out + err).strip()[:300])

        rc, out, err = run("brain-note.py", ["map", "no-such-repo", "a.ts", "-", "x"], env=ENV)
        check("note map REFUSES an unknown repo", rc != 0 and "REFUSED" in out,
              "a silent success writing an unresolvable row is worse than an error")

        # --- 2b. the key guard ---------------------------------------------------------
        # brain-note.py refuses or warns on a key the read path cannot retrieve. These cases
        # exist because the guard is only consulted by the HELPER: a raw SQL UPDATE bypasses it
        # entirely, which is how a 62-char kebab key got written during this package's own build.
        import importlib.util
        spec = importlib.util.spec_from_file_location("bn", os.path.join(HERE, "brain-note.py"))
        bn = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bn)

        def warns(key, needle):
            return any(needle in w for w in bn.check_key(key))

        long_kebab = "opencode-plugin-tool-parts-not-claude-tool_use-message-content"
        check("key guard: 62-char kebab key is flagged", len(long_kebab) == 62
              and warns(long_kebab, "segment matching only applies under 60"),
              "over 60 chars, per-segment matching silently switches off -- the exact property "
              "that makes a kebab key retrievable")
        check("key guard: a 45-char kebab key is accepted",
              not bn.check_key("opencode-plugin-tool-parts-vs-claude-tool_use"),
              str(bn.check_key("opencode-plugin-tool-parts-vs-claude-tool_use")))
        check("key guard: all-stoplisted key is flagged",
              warns("npm ci fails", "NO WORD in this key survives"),
              "a clean-looking 3-word key can be wholly unretrievable: two words are under the "
              "length floor and the third is stoplisted")
        check("key guard: long prose key is flagged",
              warns("Starting a backend service against the local stack", "prose key"))
        check("key guard: a path inside a prose key is flagged",
              warns("editing config/settings.json by hand", "INVISIBLE"))

        # --- 3. recall -----------------------------------------------------------------
        def recall(prompt, session="s1", cwd=repo):
            payload = json.dumps({"prompt": prompt, "session_id": session, "cwd": cwd})
            return run("brain-recall.py", stdin=payload, env=ENV)

        rc, out, _ = recall("where does OtpThrottle live", session="r1")
        check("recall finds a symbol just written", "OtpThrottle" in out and "code_map" in out,
              out.strip()[:300] or "(silent)")
        # The negative half of the staleness check. Without it, a mutation that marks EVERY row
        # stale passes the [STALE] assertion below -- a green suite proves only what it tests.
        check("recall does NOT label a current code_map row stale", "STALE" not in out,
              out.strip()[:300])

        rc, out, _ = recall("anything on the kafka retry topic", session="r2")
        check("recall finds a fact by its key words", "retry" in out.lower(),
              out.strip()[:300] or "(silent)")

        rc, out, _ = recall("write me a haiku about the weather", session="r3")
        check("recall is SILENT on an unrelated prompt", out.strip() == "",
              out.strip()[:200])

        rc, out, _ = recall("<task-notification>a background job finished</task-notification>",
                            session="r4")
        check("recall is SILENT on a machine-generated prompt", out.strip() == "",
              "a notification envelope drew a full injection matched on its own boilerplate, "
              "14% of everything delivered over 50 sessions")

        rc, out, _ = recall("acmecorp deploy question", session="r5")
        check("BRAIN_STOP_EXTRA suppresses the org name", out.strip() == "", out.strip()[:200])

        rc, out, _ = recall("where does OtpThrottle live", session="r1")
        check("recall does not re-deliver to the same session", "OtpThrottle" not in out,
              "the delivered log exists so a long session is not handed the same row every turn")

        # The staleness seam: edit the file so HEAD no longer matches the stored blob sha.
        open(os.path.join(repo, "src", "throttle.ts"), "a").write("// changed\n")
        subprocess.run(["git", "commit", "-qam", "change"], cwd=repo, check=True)
        rc, out, _ = recall("where does OtpThrottle live", session="r6")
        check("recall labels a drifted code_map row [STALE]", "STALE" in out,
              out.strip()[:300] or "(silent)")

        # --- 4. capture, both harnesses ------------------------------------------------
        HUNTS = [("Read", {"file_path": f"/x/file{i}.ts"}, False) for i in range(10)]
        WROTE_FACT = [("Bash", {"command": f"python3 {HERE}/brain-note.py fact a b 'c' 'd'"}, False)]
        WROTE_MAP = [("Bash", {"command": f"python3 {HERE}/brain-note.py map r p s 'x'"}, False)]
        FAILS = [("Bash", {"command": "npm ci"}, True) for _ in range(3)]

        def capture(tools, session, harness):
            if harness == "claude":
                t = os.path.join(tmp, f"transcript-{session}.jsonl")
                claude_transcript(t, tools)
                payload = json.dumps({"session_id": session, "transcript_path": t})
                return run("brain-capture.py", stdin=payload, env=ENV)
            payload = json.dumps({"sessionID": session, "messages": opencode_messages(tools)})
            return run("brain-capture.py", ["--harness", "opencode"], stdin=payload, env=ENV)

        cases = [
            ("hunted hard, wrote nothing -> nudge",      HUNTS,                True,  None),
            ("wrote a fact but no map row -> map nudge", HUNTS + WROTE_FACT,   True,  "map row still owed"),
            ("wrote a map row -> silent",                HUNTS + WROTE_MAP,    False, None),
            ("browsed a little -> silent",               HUNTS[:3],            False, None),
            ("3 failures then an edit -> nudge",         FAILS + [("Edit", {}, False)], True, None),
        ]
        for label, tools, want, needle in cases:
            for harness in ("claude", "opencode"):
                sid = f"cap-{harness}-{abs(hash(label))}"
                rc, out, err = capture(tools, sid, harness)
                fired = "BRAIN CAPTURE" in out
                check(f"[{harness}] {label}", fired == want,
                      f"stdout={out.strip()[:200]!r} stderr={err.strip()[:150]!r}")
                if want and needle and fired:
                    check(f"[{harness}] {label} -- right message", needle in out,
                          out.strip()[:200])

        # The seam itself: the same logical session, described in both harnesses' formats,
        # must reach the same verdict. This is the check that would have caught a reader
        # drifting from the counter.
        for label, tools, want, _ in cases:
            a = "BRAIN CAPTURE" in capture(tools, f"seam-c-{abs(hash(label))}", "claude")[1]
            b = "BRAIN CAPTURE" in capture(tools, f"seam-o-{abs(hash(label))}", "opencode")[1]
            check(f"readers agree: {label}", a == b, f"claude={a} opencode={b}")

        # Nagging is how a hook gets deleted.
        sid = "cap-once"
        first = "BRAIN CAPTURE" in capture(HUNTS, sid, "claude")[1]
        second = "BRAIN CAPTURE" in capture(HUNTS, sid, "claude")[1]
        check("capture nudges at most once per session", first and not second,
              f"first={first} second={second}")

        rc, out, _ = capture(HUNTS, "cap-reenter", "claude")
        payload = json.dumps({"session_id": "cap-reenter2", "stop_hook_active": True,
                              "transcript_path": os.path.join(tmp, "transcript-cap-once.jsonl")})
        rc, out, _ = run("brain-capture.py", stdin=payload, env=ENV)
        check("capture never re-enters after blocking", out.strip() == "", out.strip()[:200])

        # --- 5. crash safety -----------------------------------------------------------
        for script, args in (("brain-recall.py", []), ("brain-capture.py", []),
                             ("brain-capture.py", ["--harness", "opencode"])):
            rc, out, _ = run(script, args, stdin="not json at all",
                             env={**ENV, "BRAIN_DB": "/nonexistent/brain.db"})
            check(f"{script} {' '.join(args)} exits 0 on garbage input", rc == 0,
                  "a hook must never be able to wedge a session")
        con.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILED:
        print(f"FAILED {len(FAILED)} of {PASSED[0] + len(FAILED)}:")
        for f in FAILED:
            print(f"  - {f}")
        return 1
    print(f"ok - {PASSED[0]} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
