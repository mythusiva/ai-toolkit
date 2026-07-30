# delegation/ask/verify ACTIVE (full rules loaded at session start)
- Assume nothing the prompt+code do not settle -> 1-3 AskUserQuestion BEFORE planning. ExitPlanMode is DENIED until you ask, or the plan says `NO QUESTIONS: <why>`.
- No plan gate on delegation: dispatch freely. Plan (requirements + ASSUMPTIONS + units + models + proving checks) when the work is multi-unit or risky, not as a toll on every spawn.
- Unit spec: exact files/symbols, expected result, proving check. Terse imperative, no prose.
- Tiers: omit=sonnet leaf (default), haiku=opt-in for trivial fully-specified units, opus=money/security/concurrency, gemma-run.sh=pure text transforms. Only an EXPLICIT model may delegate further.
- Workers returned -> verify each + cite evidence before stop.
