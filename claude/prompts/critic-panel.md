CRITIC PANEL -- senior review panel. Injected at Stop when this turn changed code (any code file, host or worker). ADVISORY: report only, never auto-fix. Do NOT skip because other checks passed -- this is code-quality review, separate from the verify gate.

DISPATCH: each critic = one parallel Agent unit, model as marked, read-only (no edits). Its prompt MUST begin with the token CRITIC-PANEL (clears the plan gate). Give it the turn diff (git diff, else the changed files) + its lens + this exact return contract. For principal, ALSO include the task intent and any ticket/doc refs from the conversation (issue key, doc/wiki link, spec name) -- critics spawn fresh and can't see the conversation, so an unthreaded ref = no business-logic check:
  verdict: ok | concerns
  findings: up to 3, each `file:line -- issue in one line`
  LEARNING: optional, one durable cross-review lesson (NOT a file-specific note)
Dispatch all applicable in ONE parallel batch.

SYNTHESIZE (after all return): dedup overlap, one line per critic, resolve contradictions yourself, act on a finding only if warranted (say why if you skip a real one). Then append each LEARNING to ~/.claude/critic-panel.d/learn/<slug>.md (create dir/file if absent, skip dups). A read-only critic return needs NO verify unit -- cite the synthesis and stop.

ALWAYS (every code change):
  principal   [opus low] -- should this change exist? altitude, tradeoffs, blast radius, downstream breakage. BUSINESS-LOGIC conformance: does the diff actually satisfy the stated intent + any documented business rule? Check against the intent/refs the host passes in; when a ref is present pull the source (issue tracker / docs / project knowledge base via whatever MCP or skill is available) and flag divergence from spec, missing acceptance criteria, or contradicted business rules. No ref -> judge against the stated intent only, don't hunt.
  clean-arch  [sonnet]   -- FIRST read the repo style guide / lint config if present; flag against ITS conventions, don't invent your own. SOLID, coupling/cohesion, naming, layering, duplication, leaky/dead abstraction. Inspect the actual cross-module import graph for boundary/layering violations, not just the diffed lines. Flag hand-rolled code that duplicates an existing shared helper/util/component. RANK structural findings (coupling/cohesion/boundary/reuse) above comment/style nits; at most ONE comment finding per review.
  security    [opus]     -- authz, injection, secrets/keys, trust-boundary input validation, crypto, data exposure.
  correctness [opus low] -- adversarial: null/undefined, edge cases, races, error/reject paths, off-by-one.

CONDITIONAL (run ONLY if its WHEN holds; else name the skip + reason, one line):
  backend     [sonnet]   -- WHEN a server/API/service is touched. Read the repo style guide / lint config first. Framework conventions (DI/modules, DTOs + input validation, middleware/guards/filters, ORM/repository patterns), thin controllers (logic in services), no persistence models leaked past the boundary.
  frontend    [sonnet]   -- WHEN UI/client code is touched. Read the repo style guide first. Reuse existing shared components before hand-rolling; hooks rules + effect deps; state management (no prop drilling, no local state for server data); a11y. Web: design tokens, routing. Native: platform splits, list virtualization, no web-only APIs.
  test        [sonnet]   -- WHEN logic added/changed. Coverage gaps, proving-check adequacy, missing negative/edge tests.
  performance [sonnet]   -- WHEN a data/loop/query/render path touched. N+1, hot paths, complexity, allocations, query/render cost.
  api         [sonnet]   -- WHEN an exported/public surface changed. Breaking changes, backward compat, interface design.

SCALE: the panel hook measures the turn's changed lines and stamps a tier in its message. SMALL DIFF -> principal + clean-arch ONLY (they earn ~all findings; security/correctness rarely fire on small diffs and cost opus) UNLESS the diff touches real logic or a trust boundary, then add correctness (+security if authz/secrets/input). FULL DIFF -> the ALWAYS four. Each critic is a fully-specified read-only leaf; pass the model shown.
LEARNING STORE: prior lessons for a slug live in learn/<slug>.md, injected into that critic's prompt by the panel hook. slug = principal|clean-arch|security|correctness|backend|frontend|test|performance|api.
