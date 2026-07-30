---
name: feature-deep-dive
description: Investigate an existing feature to real depth — runtime behaviour, not just schema and file paths. Use when writing or reviewing a current-state doc, answering "how does X actually work here", onboarding onto a feature, or planning a change to one. Forces the eight nuance axes (identity propagation, read-path exposure, cache staleness, third-party coupling, client-vs-server gating, lifecycle non-events) that structure-only investigations miss.
user-invocable: true
allowed-tools: Read Grep Glob Bash Task
---

# Feature deep dive

**Structure is the easy half.** Tables, entity files and a service map are the part any
investigation finds by grepping. What breaks a mental model — and what breaks in production — is
runtime behaviour: whose identity a request runs as, what a cached decision still permits after the
data changed, what a third party knows independently of us, and what the code *never* does.

A current-state doc or plan is **not done** until all eight axes below are answered with
`file:line` evidence, or explicitly marked `UNVERIFIED`.

## When to invoke

- Writing or reviewing a current-state / architecture doc for an existing feature.
- Being asked "how does X work here" for anything that spans more than one service.
- Planning a change to an existing feature — the axes double as the plan's required sections.
- Preparing for a design discussion where others will probe the implementation.

## The eight axes

Answer each as a question with cited code. "I didn't find it" is a valid answer; silence is not.

1. **Data model — and which invariants the DB actually enforces.**
   For every stated rule ("one workspace per landlord", "one invite per email"), find the constraint
   or migration that enforces it. If it's only an app-level existence check, say so — that's a
   different risk. Cite the migration, not the entity decorator.

2. **Identity & context propagation.** For a request that crosses services: which identity is used
   for data scoping at each hop, and which is carried only for audit? Find the exact injection point
   (gateway header, interceptor, context builder) and one representative read of it. The question
   that exposes this: *how does user B end up seeing user A's data?* If the answer is "a header is
   substituted", quote the line that substitutes it.

3. **Read-path exposure, not just write guards.** Enumerate the queries/endpoints that return lists
   and aggregates, and how each is scoped. Guarded mutations are the easy half; a missing read filter
   leaks silently and never throws. Aggregates (totals, dashboards, exports, zips) deserve their own
   pass — they leak via sums without touching a row the user can see.

4. **Cache & staleness — the mid-session question.** For every cached authorization or context
   value: key format, TTL (prove it, including *absence* of TTL), who writes it, who invalidates it.
   Then answer explicitly: *if the underlying permission changes while the user is logged in, what
   takes effect immediately and what doesn't?* Name the staleness window.

5. **Third-party coupling.** What does an external system know or do independently of our database?
   Vendor-side identities, notifications, OTP delivery, webhooks, and config that lives only in a
   vendor dashboard. These are the nuances nobody finds by reading our repo — and the ones that can't
   be fixed later by a migration.

   *Worked example of the shape to look for:* a vendor sends the step-up OTP for a sensitive
   action, but **our** service chooses the destination — it overrides the SMS phone with the acting
   delegate's number, looked up from a **local mirror table** of vendor-side authorized users, and
   only when the actor differs from the account owner. Neither "the vendor sends it" nor "we send
   it" is the whole truth: the routing lives in a mirror table nobody would think to look for, and
   revoking access only stops reaching the delegate once a **fire-and-forget** sync deletes that
   row. Cite the equivalent `file:line` for each leg in the feature you're actually reading.
   Structure-only investigation finds none of this.

6. **Client vs server gating.** For each user-visible restriction, is it enforced server-side,
   client-side, or both? List the client checks and mark which have no server counterpart. A missing
   client check is a UX bug; a client-only check is a security hole.

7. **Lifecycle edges and non-events.** What the code *doesn't* do: statuses modelled but never set,
   rows never deleted (only flagged), notifications sent one way but not the other, jobs that don't
   exist. Search for the writer of every status value; if there is none, say it's dead.

8. **Failure & degradation.** What happens when the gate is off, the cache is empty, the entitlement
   lapses, or the vendor call fails — throw, silently no-op, or fail open? Silent no-ops and
   fail-open branches are findings, not footnotes.

## Evidence rule

Every non-obvious claim carries **three** things, not one:

1. the `repo/path/file.ts:line` reference,
2. the **actual code snippet** in a fenced block — the 2-8 lines that prove the claim, not a paraphrase,
3. a **GitHub permalink pinned to a commit SHA**:
   `https://github.com/<org>/<repo>/blob/<sha>/<path>#L<start>-L<end>`.

Pin the SHA, never `blob/master` — line numbers move and a branch link silently starts pointing at
unrelated code. Get it with `git rev-parse --short=12 origin/master` per repo.

**Resolve the line numbers against that SHA, not your local checkout.** The local working tree drifts
from master; a locally-correct line number produces a wrong permalink. Read the blob at the SHA
(`git show <sha>:<path>`), find the line by *pattern*, and take the snippet from there. Then validate:
every pinned link's blob must exist and the cited line must be within the file's length.

Two further traps:

- **Don't trust the entity/decorator for constraints** — check the migration.
- **Don't trust a doc (including your own earlier one) as a source** — re-verify against code and
  date the verification. Docs age; `file:line` from six months ago may name a moved symbol.

When delegating parts of the sweep, demand `file:line` in the return and spot-check a sample
yourself before repeating it. A subagent's confident summary is a hypothesis.

## Applying it to planning

Each axis becomes a required section of the plan, not an afterthought:

- No plan is complete if it can't say **where each new rule is enforced** (axis 3 and 6) and **what
  invalidates the cached version of it** (axis 4).
- If the change touches identity or scope, the plan states the propagation path (axis 2) and what
  happens to in-flight sessions at rollout.
- Third-party coupling (axis 5) is decided **before** build when the vendor's model can't express
  what we're promising — that class of mistake survives every later migration.
- Prefer a shadow / log-only enforcement mode for anything that filters data: it converts "we think
  nothing leaks" into a measurement before users are affected.

## Self-check before publishing

A doc or plan passes only if a new engineer could answer, from it alone:

1. How does user B see user A's data, and which id is the data actually scoped by?
2. What happens mid-session when permissions change?
3. Who receives the OTP / email / webhook — the acting user or the account owner, and why?
4. Which restrictions are server-enforced, and which are only in the client?
5. Which stated invariants the database does *not* enforce.
6. What the feature deliberately never does.

If any answer requires reading the code again, the doc isn't finished — add the section.

## Where this came from

A current-state doc for a multi-user-access feature captured the schema, the service map and ~40
`file:line` references — and still couldn't answer an eng lead's six questions: identity
substitution at the gateway, mid-session revocation, why the step-up OTP reached the delegate
rather than the account owner, and how the client-side gating layers stack. All six were
runtime-behaviour questions. The structure was thorough; the behaviour was unexamined.
