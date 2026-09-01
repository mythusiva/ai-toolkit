Every code-referencing row carries verified_at and blob_sha. Before trusting a code_map row:
  git -C <checkout> rev-parse HEAD:<path> | cut -c1-12
Matches blob_sha -> trust it. Differs -> re-verify, then UPDATE the row and bump verified_at.

AUTOMATIC (no action needed): the recall hook verifies every code_map row it injects, by
batch-checking blob_sha with one `git ls-tree` per repo. A drifted or deleted path is labelled
[STALE] inline in the recall block. If you see that label, re-read the file, then UPDATE the row
and bump verified_at IN THE SAME TURN - do not just work around it.

NOT AUTOMATIC (your job): fact and gotcha rows have no anchor, only verified_at. When you hit one
and it turns out wrong, mark it status='disproven' with the evidence that killed it -- do not
delete it, because the disproof is what stops the next agent re-deriving the dead end. When a
recipe fails, UPDATE recipe SET fail_count=fail_count+1; when it succeeds after a change, fix the
command and set last_ok_at=date('now'). Nothing else will do this for you.

SWEEP when you have slack: SELECT * FROM stale; then confirm or disprove each row.

The `stale` view deliberately EXCLUDES code_map: those rows are verified against git on every
use, so age-flagging them once marked 31 provably-current rows stale in one go. A view that cries
wolf is worse than no view. Never age-flag something already verified by a stronger signal.
