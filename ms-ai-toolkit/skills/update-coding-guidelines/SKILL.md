---
name: update-coding-guidelines
description: Update a repo's CLAUDE.md or coding style files when a new pattern, convention, or anti-pattern is discovered during work. Use proactively when you observe something noteworthy that isn't already documented.
user-invocable: true
allowed-tools: Read Edit Write Bash Grep
---

# Update Coding Guidelines

When work reveals a pattern, convention, or anti-pattern that isn't already documented, record it in the appropriate repo's CLAUDE.md before the session ends.

## When to invoke

Invoke proactively (without the user asking) when any of the following occur:

- A naming convention, file structure rule, or architectural pattern is observed that isn't written down
- A new anti-pattern is identified — especially one that caused a real bug or wasted time
- A shared utility, hook, or helper is added that others should know to reuse
- The user states a rule ("we always do X", "never do Y here") that isn't in CLAUDE.md
- A code review or PR surfaces a pattern that would benefit future contributors

Do NOT invoke for:
- Things directly readable from the code (naming is self-evident, structure is obvious)
- In-progress migration state or temporary workarounds
- Patterns scoped to a single file — too narrow to generalize
- Anything already documented in the target file

## Which file to update

Resolve the target for the repo the pattern came from, in this order:

1. An existing guidelines file at the repo root — `CLAUDE.md`, or whatever it
   symlinks to (`AGENTS.md`), else `CONTRIBUTING.md` / `coding-standards/`.
2. A monorepo package's own `CLAUDE.md` when the pattern is package-scoped —
   the nearest one above the changed files, not the workspace root.
3. No such file yet → create `CLAUDE.md` at the repo root.

Never write the pattern into a different repo than the one it applies to.

## Process

### Step 1 — Read before writing
Read the target CLAUDE.md in full. Confirm the pattern isn't already covered. Identify the right section to add to (or whether a new section is warranted).

### Step 2 — Write the entry

Each entry must include:

1. **The rule** — one clear sentence: what to do or not do
2. **Why** — one sentence on the motivation (prevents a real bug, enforces consistency, avoids tech debt)
3. **Code example** (when applicable) — use CORRECT / WRONG labels, not GOOD/BAD

```javascript
// CORRECT
const firstName = useFirstName();

// WRONG — causes unnecessary re-renders
const { firstName } = useUserStore();
```

Keep it minimal. One pattern per entry. No padding or generic advice.

### Step 3 — Place it in context

Add to the most relevant existing section. Common sections across repos:

- **Anti-Patterns / Critical Rules** — things that are prohibited
- **Required Patterns** — things that must always be done a certain way
- **Architecture** — structural or module-level conventions
- **Testing** — test file location, naming, patterns
- **Code Standards / Naming Conventions** — formatting and naming rules

If no section fits, add a new one with a clear header.

### Step 4 — Confirm with the user

After editing, mention what was added and where — one sentence. Don't ask for permission first unless the change is substantial or touches a "Critical Rules" section.

## Size guard

A guidelines file loaded into every session earns its size. Treat ~30k
characters as the working target and 40k as the cap:

```bash
wc -c <target-file>
```

Near the limit → put the pattern in a focused skill under the repo's
`.claude/skills/` instead of growing the always-loaded file.
