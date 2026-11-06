# Director tick

Read `rules.md` first if it isn't in context. Run every step, in order.

Every fork goes to the user as a question (C2). A tick never merges or posts on its own.

1. **Schedule:** `crontab -l` against `schedule.md`. A missing row → re-add it now.
2. **Matrix:** `scripts/mx.py read`. Answer the user there. A numbered reply to a `pending-q` = the
   user's answer: act on it and drop the `pending-q` line from the handoff log.
3. **Sessions:** `agent-manager sessions --json`. Archived-but-running, or idle with its job done
   → kill, then archive. Archived but still working → ask the user in one table before killing.
4. **Work in flight:** for each open ticket or PR that is ours, name the next step that moves it
   along and do it, or dispatch a worker session for it.
5. **Merge:** complete units that are approved, green, with no open threads and no DO NOT MERGE,
   meeting S1–S3: recommend to the user. Merge only on the user's yes, then S4–S6.
6. **Feedback:** new review comments on our PRs and mentions about our work. Fix what they ask
   (a worker session if it is code). Reply on the PR directly; elsewhere only per C1.
7. **Standing checks:** <!-- project-specific recurring checks go here -->
8. **Log:** one line in `handoff-log.md`: what you merged, moved or posted this tick.

Never end a tick just waiting for relays.
