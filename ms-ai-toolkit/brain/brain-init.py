#!/usr/bin/env python3
"""Create or upgrade the brain database, and seed the guide the agents read.

Idempotent: every statement is CREATE IF NOT EXISTS, and the guide topics are INSERT OR REPLACE
from guide/*.md, so re-running it after a package update refreshes the protocol without touching
a single fact you have written.

  brain-init.py            # create/upgrade at $BRAIN_DB, seed guide from guide/
  brain-init.py --guide    # reseed the guide topics only
"""
import glob, os, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import brainlib

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS guide (
  topic      TEXT PRIMARY KEY,
  body       TEXT NOT NULL,
  updated_at TEXT NOT NULL DEFAULT (date('now'))
);

CREATE TABLE IF NOT EXISTS fact (
  id          INTEGER PRIMARY KEY,
  scope       TEXT NOT NULL,                 -- repo name, 'global', or a feature slug
  subject     TEXT NOT NULL,                 -- short handle you would grep for
  claim       TEXT NOT NULL,
  evidence    TEXT NOT NULL,
  verified_at TEXT NOT NULL DEFAULT (date('now')),
  status      TEXT NOT NULL DEFAULT 'active'
                CHECK (status IN ('active','superseded','disproven','hypothesis')),
  supersedes  INTEGER REFERENCES fact(id),
  tags        TEXT,
  source      TEXT                           -- session id / PR / doc that produced it
);

CREATE TABLE IF NOT EXISTS code_map (
  id          INTEGER PRIMARY KEY,
  repo        TEXT NOT NULL,
  path        TEXT NOT NULL,
  symbol      TEXT,
  kind        TEXT,                          -- file | class | function | table | route | env | flag | test
  summary     TEXT NOT NULL,
  line        INTEGER,
  blob_sha    TEXT,
  verified_at TEXT NOT NULL DEFAULT (date('now')),
  UNIQUE (repo, path, symbol)
);

CREATE TABLE IF NOT EXISTS gotcha (
  id          INTEGER PRIMARY KEY,
  scope       TEXT NOT NULL,
  trigger     TEXT NOT NULL,                 -- the command shape or situation that hits it
  symptom     TEXT NOT NULL,                 -- the error text you would actually see
  cause       TEXT,
  fix         TEXT NOT NULL,
  verified_at TEXT NOT NULL DEFAULT (date('now')),
  hits        INTEGER NOT NULL DEFAULT 1     -- bump when it bites again; high hits = fix the root cause
);

CREATE TABLE IF NOT EXISTS recipe (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL UNIQUE,
  scope      TEXT NOT NULL,
  goal       TEXT NOT NULL,
  command    TEXT NOT NULL,
  notes      TEXT,
  last_ok_at TEXT,
  ok_count   INTEGER NOT NULL DEFAULT 0,
  fail_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS decision (
  id         INTEGER PRIMARY KEY,
  topic      TEXT NOT NULL,
  question   TEXT NOT NULL,
  chosen     TEXT NOT NULL,
  rejected   TEXT,
  rationale  TEXT NOT NULL,
  decided_at TEXT NOT NULL DEFAULT (date('now')),
  decided_by TEXT,                           -- 'user' | 'agent' | name
  doc        TEXT,
  status     TEXT NOT NULL DEFAULT 'active'
               CHECK (status IN ('active','revisited','reversed'))
);

CREATE TABLE IF NOT EXISTS work_log (
  id         INTEGER PRIMARY KEY,
  session    TEXT NOT NULL,
  agent      TEXT,
  scope      TEXT NOT NULL,
  branch     TEXT,
  task       TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'open'
               CHECK (status IN ('open','blocked','done','abandoned')),
  note       TEXT,
  artifacts  TEXT,                           -- PR urls, file paths, doc paths
  started_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Inbound items you may or may not act on. `verdict` on a 'declined' row is the one thing no
-- upstream system records: why you consciously left something alone.
CREATE TABLE IF NOT EXISTS thread (
  id          INTEGER PRIMARY KEY,
  source      TEXT NOT NULL,                 -- slack | github | jira | datadog | ...
  external_id TEXT NOT NULL,
  title       TEXT NOT NULL,
  url         TEXT,
  who         TEXT,
  state       TEXT NOT NULL DEFAULT 'new'
                CHECK (state IN ('new','acting','declined','done')),
  verdict     TEXT,
  first_seen  TEXT NOT NULL DEFAULT (datetime('now')),
  last_seen   TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (source, external_id)
);

-- Keyed on (day,metric) so concurrent snapshots are idempotent rather than racing.
CREATE TABLE IF NOT EXISTS health (
  day     TEXT NOT NULL,
  metric  TEXT NOT NULL,
  value   REAL NOT NULL,
  PRIMARY KEY (day, metric)
);

-- How often YOU type each word, rebuilt from your own prompt history. A word you use in more
-- than BRAIN_COMMON_DF of your prompts is a function word for you, whatever a dictionary says.
-- Missing or empty simply makes that rule inert.
CREATE TABLE IF NOT EXISTS term_df (term TEXT PRIMARY KEY, prompts INTEGER NOT NULL);

CREATE INDEX IF NOT EXISTS idx_fact_scope   ON fact(scope, status);
CREATE INDEX IF NOT EXISTS idx_fact_subject ON fact(subject);
CREATE INDEX IF NOT EXISTS idx_map_symbol   ON code_map(symbol);
CREATE INDEX IF NOT EXISTS idx_map_path     ON code_map(repo, path);
CREATE INDEX IF NOT EXISTS idx_gotcha_scope ON gotcha(scope);
CREATE INDEX IF NOT EXISTS idx_work_status  ON work_log(status, scope);
CREATE INDEX IF NOT EXISTS thread_open      ON thread(state, last_seen);

-- One view every reader queries, so recall never has to know about five tables. A disproven
-- fact stays visible and shouts, because the disproof is what stops the next agent re-deriving
-- the dead end. Rows scoped 'agent-brain' are excluded on purpose: lessons about the brain
-- itself belong in the guide, not in recall results.
DROP VIEW IF EXISTS search;
CREATE VIEW search AS
  SELECT 'fact' AS kind, id, scope, subject AS key,
         CASE WHEN status='disproven' THEN 'DISPROVEN - DO NOT ACT ON THIS: ' ELSE '' END
           || claim || ' || ' || evidence AS body, verified_at
    FROM fact WHERE status IN ('active','disproven') AND scope <> 'agent-brain'
  UNION ALL
  SELECT 'code_map', id, repo, COALESCE(symbol, path), path || ' :: ' || summary, verified_at
    FROM code_map
  UNION ALL
  SELECT 'gotcha', id, scope, trigger, symptom || ' -> ' || fix, verified_at
    FROM gotcha WHERE scope <> 'agent-brain'
  UNION ALL
  SELECT 'recipe', id, scope, name, goal || ' :: ' || command, COALESCE(last_ok_at,'')
    FROM recipe WHERE name NOT LIKE 'brain.%'
  UNION ALL
  SELECT 'decision', id, topic, question,
         chosen || ' (rejected: ' || COALESCE(rejected,'-') || ') because ' || rationale, decided_at
    FROM decision WHERE status <> 'reversed' AND topic <> 'agent-brain';

-- Only rows with NO other verification path. code_map is deliberately absent: every row is
-- checked against git on every use, so age-flagging them marked 31 provably-current rows stale
-- in one go -- a false-alarm flood that teaches its reader to ignore the view. Never age-flag
-- something already verified by a stronger signal.
DROP VIEW IF EXISTS stale;
CREATE VIEW stale AS
  SELECT 'fact' AS kind, id, scope, subject AS key, verified_at,
         'no anchor - re-verify the claim or disprove it' AS why
    FROM fact WHERE status='active' AND verified_at < date('now','-60 day')
  UNION ALL
  SELECT 'gotcha', id, scope, trigger, verified_at,
         'no anchor - does this still bite?'
    FROM gotcha WHERE verified_at < date('now','-90 day')
  UNION ALL
  SELECT 'recipe', id, scope, name, COALESCE(last_ok_at,'never'),
         'not confirmed working since last_ok_at'
    FROM recipe WHERE last_ok_at IS NULL OR last_ok_at < date('now','-60 day');
"""


def seed_guide(con):
    """guide/*.md -> guide rows. The filename is the topic, so ordering is lexical and the
    agents read 00 first. A doc that must be hand-synchronised with a live system is wrong by
    default: these files ARE the source, and the DB is a cache of them."""
    n = 0
    for f in sorted(glob.glob(os.path.join(brainlib.SCRIPTS, "guide", "*.md"))):
        topic = os.path.splitext(os.path.basename(f))[0]
        body = open(f).read().strip()
        # Path placeholders resolve at seed time, so a guide the agent reads never names a
        # path that does not exist on this machine.
        body = (body.replace("@DB@", brainlib.DB)
                    .replace("@SCRIPTS@", brainlib.SCRIPTS)
                    .replace("@HOME@", brainlib.HOME))
        con.execute("INSERT OR REPLACE INTO guide(topic,body,updated_at) "
                    "VALUES(?,?,date('now'))", (topic, body))
        n += 1
    return n


def main():
    os.makedirs(os.path.dirname(brainlib.DB) or ".", exist_ok=True)
    fresh = not os.path.exists(brainlib.DB)
    con = sqlite3.connect(brainlib.DB, timeout=10)
    guide_only = "--guide" in sys.argv
    with con:
        if not guide_only:
            con.executescript(SCHEMA)
            for k, v in (("schema_version", "2"), ("owner", "agents"),
                         ("purpose", "Agent-only working memory. Not read by humans. "
                                     "Restructure freely -- see guide topic 05_restructuring."),
                         ("path", brainlib.DB)):
                con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (k, v))
            con.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('created',date('now'))")
        n = seed_guide(con)
    ok = con.execute("PRAGMA integrity_check").fetchone()[0]
    rows = con.execute("SELECT count(*) FROM search").fetchone()[0]
    con.close()
    print(f"{'created' if fresh else 'upgraded'} {brainlib.DB}")
    print(f"  integrity_check: {ok}")
    print(f"  guide topics seeded: {n}")
    print(f"  searchable rows: {rows}")
    if fresh:
        print(f"\nNext: read the protocol the agents read --")
        print(f"  sqlite3 {brainlib.DB} \"SELECT topic,body FROM guide;\"")
    return 0 if ok == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
