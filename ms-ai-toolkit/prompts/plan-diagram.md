# Plan diagram format

Terminal-facing plans (ExitPlanMode, shown in the CLI) MUST NOT use ```mermaid -- it renders as raw text.
Use ASCII: SINGLE-COLUMN vertical top-down, one step per left-aligned line, connected by `│` then `▼`
placed at ONE FIXED indent column (e.g. 6 spaces) between steps -- the fixed indent is what keeps it aligned.

    web client: signIn.start()
    │
    ▼  credential captured
    api gateway: session gate
    │
    ▼  device-key row present?
    IdP mints session token

- Branches/comparisons = SEPARATE STACKED flows, labelled `BEFORE:` / `AFTER:` or `path A:` / `path B:`. Never side-by-side columns.
- One short annotation per line. No diagonal `\ /` connectors, no inline math clutter, no multi-column boxes.
- Plain markdown table only for purely tabular data with no flow.
- One concern per diagram, ~5-12 nodes. Split rather than cram. Trivial single-step plans skip it.

```mermaid only when the plan is written to a file / PR body / Artifact that renders it: sequence for
request/handshake flows, flowchart for branching, stateDiagram for lifecycles, erDiagram for schema.
