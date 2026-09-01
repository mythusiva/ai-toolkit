Several agents (background jobs, subagents, worktrees) share this one file. WAL is on, so
concurrent readers are fine and writes serialise. Rules:
  * Claim before you touch: INSERT INTO work_log before editing a branch or file set.
  * Check work_log for open rows on the same scope/branch first.
  * Keep writes small and committed immediately; never hold a transaction open across tool calls.
  * If sqlite3 reports "database is locked", retry: sqlite3 -cmd ".timeout 5000" ...
  * CLOSE your row when done. A stale `open` row is worse than no row, because it makes the next
    agent believe work is in flight: brain-note.py done <id>

Load-tested: 30 simultaneous operations - 12 recall hooks, 8 health snapshots, 10 writes -
produced zero failures and integrity_check ok. Two things make that hold: WAL mode, and
INSERT OR REPLACE keyed on (day,metric) so concurrent snapshots are idempotent rather than
racing. If you add a writer, key it the same way.
