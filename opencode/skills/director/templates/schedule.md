# Director schedule: the only list

Wake-ups come from the system crontab via `scripts/tick.sh`, which reads `director.id` and queues
the prompt with `agent-manager send`. A schedule change → edit this table and run
`scripts/install-schedule.sh` in the same turn. A row not in this table is not installed.

Times are local. Weekdays every 30 min during work hours, hourly otherwise.

| # | Cron | Prompt |
|---|---|---|
| 1 | `7,37 9-18 * * 1-5` | Director tick: run $DIRECTOR_HOME/tick.md step by step. |
| 2 | `23 0-8,19-23 * * *` | Director tick: run $DIRECTOR_HOME/tick.md step by step. |
| 3 | `23 9-18 * * 0,6` | Director tick: run $DIRECTOR_HOME/tick.md step by step. |
