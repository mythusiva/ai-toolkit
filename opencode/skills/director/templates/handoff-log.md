# Director handoff log

Append-only. One line per tick; one `## Handoff` section per handoff. A new director reads only
the last `## Handoff` section (`grep -n '^## Handoff' handoff-log.md | tail -1`).

## Handoff YYYY-MM-DD HH:MM (<old id> -> successor)
- Goal: <the user's current goal, verbatim>
- Open: <next steps, most important first>
- pending-q <topic>: <question already asked of the user and not yet answered, with its numbered options>
- Reporting to the director: <session ids and what each is doing>
- In flight: <merges being watched, deploys, long-running jobs>
