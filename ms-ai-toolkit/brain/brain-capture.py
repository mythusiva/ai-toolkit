#!/usr/bin/env python3
"""End-of-turn hook: if this session clearly LEARNED something and wrote none of it down, say so once.

Measured over the brain's first 3 days: 6 sessions showed clear evidence of learning (heavy
hunting, or recovering from repeated command failures) and only 2 wrote anything back -- a 33%
capture rate. Recall is only ever as good as what capture puts in it.

This is the component that actually drives capture. The agent-brain SKILL was invoked ZERO times
over the same period while this nudge converted 4 of 4 INDEPENDENT sessions into writes. A skill
competing with a hook for the same trigger always loses: the hook fires on EVIDENCE, the skill
fires on the model remembering to look.

It does NOT fire on a schedule or on every turn. It fires when the transcript itself shows
learning happened and the database did not change, and at most once per session. A sibling
Stop hook was deleted after firing 687 times; the difference here is that the trigger is
evidence, not the clock.

Two harnesses, one counter. `read_claude` and `read_opencode` normalise their very different
transcript shapes into the same event stream, and `count` is the single place the thresholds
live. Components correct against their own spec are still wrong together, so the seam is one
function wide and brain-selftest.py pushes a value through both readers.

Usage:
  brain-capture.py                       # Claude Code Stop hook: payload on stdin, JSON out
  brain-capture.py --harness opencode    # opencode: {sessionID, messages:[...]} in, text out
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brainlib

MARKER_DIR = os.environ.get("BRAIN_CAPTURE_DIR", os.path.join(brainlib.HOME, "capture.d"))
FAIL_MIN = 3     # failed tool results in the session
HUNT_MIN = 8     # search/read/delegate calls -- someone was looking for something

# opencode names its tools in lower case and calls delegation `task`. Normalising here rather
# than teaching `count` about both keeps the thresholds comparable across harnesses.
ALIASES = {"bash": "Bash", "edit": "Edit", "write": "Write", "read": "Read",
           "grep": "Grep", "glob": "Glob", "task": "Agent", "webfetch": "WebFetch",
           "patch": "Edit", "multiedit": "Edit", "list": "Glob", "todowrite": "TodoWrite"}


def canon(name):
    return ALIASES.get((name or "").lower(), name or "")


def count(events):
    """Fold a normalised event stream into the five numbers the nudge decides on.

    An event is {kind: 'tool_use'|'tool_result', name, input, is_error}. Returns
    (fails, hunts, edits, wrote, wrote_map, hunted_for).
    """
    fails = hunts = edits = 0
    wrote = wrote_map = False
    hunted_for = []
    for e in events:
        if e.get("kind") == "tool_result":
            if e.get("is_error"):
                fails += 1
            continue
        if e.get("kind") != "tool_use":
            continue
        n, i = canon(e.get("name")), (e.get("input") or {})
        cmd = str(i.get("command") or "")

        # A write must be an actual Bash command, NOT any text mentioning the db. A substring
        # test over the raw transcript line let a RECALL INJECTION fake it: the injection header
        # names the db and any surfaced row containing INSERT or UPDATE sits on the same line, so
        # the nudge was suppressed exactly when the brain had been read and not written.
        if n == "Bash":
            if re.search(r"brain\.db|agent-brain\.db", cmd) and re.search(r"\b(INSERT|UPDATE)\b", cmd):
                wrote = True
            if "brain-note.py" in cmd:
                wrote = True
            if re.search(r"brain-note\.py\s+map\b", cmd) or re.search(r"INSERT\s+INTO\s+code_map\b", cmd, re.I):
                wrote_map = True

        if n in ("Edit", "Write"):
            edits += 1
        # Count every shape of exploration, not just Grep. Measured over the monitoring window:
        # ZERO Grep/Glob calls, while sessions explored with Bash (600), Read (54) and Agent (16).
        # Counting Grep alone made real learning invisible, so the nudge never fired and
        # capture_rate was measured against the wrong denominator.
        if n in ("Grep", "Glob"):
            hunts += 1
            if i.get("pattern"):
                hunted_for.append(str(i["pattern"])[:40])
        elif re.match(r"\s*(grep|rg|find)\b", cmd) or " grep " in cmd:
            hunts += 1
            m = re.search(r"""['"]([^'"]{4,40})['"]""", cmd)
            if m:
                hunted_for.append(m.group(1))
        elif n == "Read":
            hunts += 1
            fp = i.get("file_path") or i.get("filePath") or i.get("path") or ""
            if fp:
                hunted_for.append(os.path.basename(str(fp))[:40])
        elif n == "Agent" or n.startswith("mcp__"):
            hunts += 1
    return fails, hunts, edits, wrote, wrote_map, hunted_for


def read_claude(tpath):
    """Claude Code transcript: JSONL, one message per line, tools inside message.content[]."""
    for line in open(tpath, errors="replace"):
        try:
            d = json.loads(line)
        except Exception:
            continue
        c = (d.get("message") or {}).get("content")
        if not isinstance(c, list):
            continue
        for it in c:
            if not isinstance(it, dict):
                continue
            if it.get("type") == "tool_result":
                yield {"kind": "tool_result", "is_error": bool(it.get("is_error"))}
            elif it.get("type") == "tool_use":
                yield {"kind": "tool_use", "name": it.get("name"), "input": it.get("input") or {}}


def read_opencode(messages):
    """opencode session messages: [{info, parts:[...]}], tools are parts of type 'tool'.

    One part carries both the call and its result -- `state.status == 'error'` is the failed
    tool result, so each tool part yields a tool_use and, when it failed, a tool_result too.
    """
    for msg in messages or []:
        for part in (msg.get("parts") or []):
            if part.get("type") != "tool":
                continue
            state = part.get("state") or {}
            yield {"kind": "tool_use", "name": part.get("tool"),
                   "input": state.get("input") or {}}
            if state.get("status") == "error":
                yield {"kind": "tool_result", "is_error": True}


def advice(note_cmd):
    """Health-trend advice, if the daily snapshot has produced any. This nudge is the moment
    it is relevant -- nobody reads a table on a schedule."""
    try:
        import sqlite3
        con = sqlite3.connect(f"file:{brainlib.DB}?mode=ro", uri=True, timeout=2)
        row = con.execute("SELECT body FROM guide WHERE topic='08_current_advice'").fetchone()
        con.close()
        if row and "Act on these" in row[0]:
            return "\n\nFrom the health trend:\n" + row[0]
    except Exception:
        pass
    return ""


def build_reason(fails, hunts, wrote, wrote_map, hunted_for, note_cmd):
    """The nudge text, or None if this session owes nothing. Pure, so the suite can assert it."""
    learned = fails >= FAIL_MIN or hunts >= HUNT_MIN
    if not learned:
        return None
    # `wrote` used to return early here, so ONE fact write bought silence for a whole session.
    # Measured: fact +20, gotcha +12, recipe +2, decision +4 over two days while code_map stayed
    # flat -- those sessions wrote something, so they were never asked for the map row they owed.
    map_only = wrote
    if map_only and (wrote_map or hunts < HUNT_MIN):
        return None
    top = ", ".join(dict.fromkeys(hunted_for[:6])) or "several symbols"
    extra = advice(note_cmd)

    if map_only:
        return (
            "BRAIN CAPTURE - map row still owed. You wrote to the brain, but not a `code_map` "
            f"row, and {hunts} calls went into locating things ({top}).\n\n"
            "code_map is the table that removes orientation cost (median 15 tool calls before "
            "the first edit) and it is the one that gets skipped. One line, anchors filled in "
            "for you:\n"
            f"  {note_cmd} map <repo> <path> <symbol|-> \"<what it does, what is surprising>\"\n\n"
            "If you genuinely located nothing worth the next agent's time, say so in one line "
            "and stop - this will not ask again in this session." + extra)

    why = []
    if fails >= FAIL_MIN:
        why.append(f"{fails} tool calls failed before something worked (that is a `gotcha`, "
                   f"or a `recipe` whose ceremony you had to rediscover)")
    if hunts >= HUNT_MIN:
        why.append(f"{hunts} searches went into locating things ({top}) - each one you found "
                   f"is a `code_map` row the next agent will not have to hunt for")
    return (
        "BRAIN CAPTURE. This session shows evidence of learning and the brain did not "
        "change:\n  - " + "\n  - ".join(why) + "\n\n"
        "Write what you learned before stopping. Cheapest path, anchors filled in for you:\n"
        f"  {note_cmd} map <repo> <path> <symbol|-> \"<what it does, what is surprising>\"\n"
        f"  {note_cmd} gotcha <scope> \"<trigger>\" \"<symptom>\" \"<fix>\"\n"
        f"  {note_cmd} recipe <name> <scope> \"<goal>\" \"<command>\"\n\n"
        "If nothing here is worth the next agent's time, say so in one line and stop - this "
        "will not ask again in this session." + extra)


def main():
    harness = "opencode" if "--harness" in sys.argv and "opencode" in sys.argv else "claude"
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    note_cmd = f"python3 {os.path.join(brainlib.SCRIPTS, 'brain-note.py')}"

    if harness == "opencode":
        sid = payload.get("sessionID") or "nosession"
        events = read_opencode(payload.get("messages"))
    else:
        if payload.get("stop_hook_active"):
            return 0            # never re-enter: we already blocked and the model is stopping again
        sid = payload.get("session_id") or "nosession"
        tpath = payload.get("transcript_path") or ""
        if not tpath or not os.path.exists(tpath):
            return 0
        events = read_claude(tpath)

    os.makedirs(MARKER_DIR, exist_ok=True)
    marker = os.path.join(MARKER_DIR, sid)
    if os.path.exists(marker):
        return 0                # already nudged this session; nagging is how a hook gets deleted

    fails, hunts, edits, wrote, wrote_map, hunted_for = count(events)
    # A session that only read and never edited was browsing, not learning.
    if edits == 0 and hunts < HUNT_MIN:
        return 0
    reason = build_reason(fails, hunts, wrote, wrote_map, hunted_for, note_cmd)
    if reason is None:
        return 0

    open(marker, "w").write("1")
    brainlib.prune_markers(MARKER_DIR)
    if harness == "opencode":
        print(reason)           # the plugin injects this into the next turn; opencode cannot block
    else:
        print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)   # a capture nudge must never be able to wedge a session
