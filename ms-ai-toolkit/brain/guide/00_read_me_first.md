This database is agent working memory. Humans never read it.
OPEN WITH:  sqlite3 -header -column @DB@

ALWAYS start a task with ONE query before you grep or read anything:
  SELECT kind,key,body,verified_at FROM search WHERE body LIKE '%TERM%' OR key LIKE '%TERM%' LIMIT 20;
Then read the tables that matched. Cost is one tool call; it replaces the 15-call median
orientation sweep measured across 251 editing sessions.

You will usually not need that query, because a recall hook runs it for you on every prompt and
injects the hits. Run it by hand when the hook stayed silent and you still suspect something is
recorded -- and when that happens, read topic 09_lessons on why keys go unretrievable.

If you are about to CHANGE this system rather than use it, read 09_lessons FIRST. It is
31 monitoring passes of hard-won failure modes, compressed - every one of them silent.
