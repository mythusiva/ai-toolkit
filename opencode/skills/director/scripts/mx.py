#!/usr/bin/env python3
"""Director <-> user over Matrix, the away channel.

Usage: mx.py login | room | post "<text>" | read

Env: MATRIX_HOMESERVER (https://matrix.example.org), MATRIX_OWNER (@you:example.org, the only
account whose messages count), MATRIX_USER (the bot's user name), MATRIX_PASSWORD (login only),
MATRIX_STATE_DIR (default ~/.config/director-matrix). The room must stay unencrypted: this client
cannot read encrypted replies, so post refuses an encrypted room.
"""
import json, os, sys, urllib.parse, urllib.request, uuid

DIR = os.path.expanduser(os.environ.get("MATRIX_STATE_DIR", "~/.config/director-matrix"))
STATE = os.path.join(DIR, "state.json")


def env(name):
    v = os.environ.get(name)
    if not v:
        sys.exit(f"set {name}")
    return v


def load():
    return json.load(open(STATE)) if os.path.exists(STATE) else {}


def save(s):
    os.makedirs(DIR, exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(s, f, indent=1)
    os.chmod(STATE, 0o600)


def api(method, path, body=None, token=None):
    req = urllib.request.Request(env("MATRIX_HOMESERVER").rstrip("/") + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def login(s):
    r = api("POST", "/_matrix/client/v3/login", {
        "type": "m.login.password", "identifier": {"type": "m.id.user", "user": env("MATRIX_USER")},
        "password": env("MATRIX_PASSWORD"), "initial_device_display_name": "director"})
    s.update(user_id=r["user_id"], token=r["access_token"])
    s.pop("since", None)
    save(s)
    print("logged in as", r["user_id"])


def room(s):
    owner = env("MATRIX_OWNER")
    r = api("POST", "/_matrix/client/v3/createRoom",
            {"name": "Director", "preset": "private_chat", "invite": [owner]}, s["token"])
    s["room_id"] = r["room_id"]
    s.pop("since", None)
    save(s)
    print("room", r["room_id"], "invited", owner)


def post(s, text):
    rid = urllib.parse.quote(s["room_id"])
    if any(e.get("type") == "m.room.encryption" for e in api("GET", f"/_matrix/client/v3/rooms/{rid}/state", token=s["token"])):
        sys.exit("room is encrypted; this client cannot read replies there")
    api("PUT", f"/_matrix/client/v3/rooms/{rid}/send/m.room.message/{uuid.uuid4().hex}",
        {"msgtype": "m.text", "body": text}, s["token"])
    print("posted")


def read(s):
    owner = env("MATRIX_OWNER")
    flt = urllib.parse.quote(json.dumps({"room": {"rooms": [s["room_id"]], "timeline": {"limit": 50}}}))
    q = f"?timeout=0&filter={flt}" + (f"&since={s['since']}" if s.get("since") else "")
    r = api("GET", "/_matrix/client/v3/sync" + q, token=s["token"])
    first = not s.get("since")
    s["since"] = r["next_batch"]
    save(s)
    if first:
        print("(first read: watermark set, older messages skipped)")
        return
    evs = r.get("rooms", {}).get("join", {}).get(s["room_id"], {}).get("timeline", {}).get("events", [])
    msgs = [e for e in evs if e.get("type") == "m.room.message" and e.get("sender") == owner]
    for e in msgs:
        print(f"{e['origin_server_ts']} {e['content'].get('body', '')}")
    if not msgs:
        print("no new messages")


if __name__ == "__main__":
    s = load()
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "login":
        login(s)
    elif cmd == "room":
        room(s)
    elif cmd == "post":
        post(s, " ".join(sys.argv[2:]))
    elif cmd == "read":
        read(s)
    else:
        sys.exit(__doc__)
