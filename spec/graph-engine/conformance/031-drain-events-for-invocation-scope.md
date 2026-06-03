# 031 — drain_events_for Invocation Scope

The drain primitive scopes strictly to the supplied `invocation_id`.
Events tagged with a different `invocation_id` do not affect the
drain's completion or appear in the per-invocation accumulator bucket.
Two serial invocations of the same compiled graph demonstrate the
scoping: each invocation gets a fresh `invocation_id` (per §5.1) and
each terminal-node drain sees only its own invocation's events.

**Spec sections exercised:**

- §6 *Per-invocation drain* — events are scoped via the
  `invocation_id` propagated through the observability §3.4
  contextvar mechanism.
- §6 *Per-invocation drain* — events tagged with a different
  `invocation_id` do not affect the drain's completion.
- §6 *Per-invocation drain* — composition with resume: a resumed
  invocation mints a fresh `invocation_id`; the drain scopes to the
  resumed invocation's events only. (Resume is not exercised here
  directly — that mechanism lands in pipeline-utilities §10 /
  proposal 0021 — but the per-id scoping rule the resume case
  relies on is the rule this fixture pins down.)

**What passes:**

- Each invocation gets a fresh, unique `invocation_id` (per §5.1).
- The terminal-node drain in invocation `first` returns with the
  accumulator bucket containing only `first`'s events.
- The terminal-node drain in invocation `second` returns with the
  accumulator bucket containing only `second`'s events — `first`'s
  events do NOT bleed into `second`'s bucket.

**What fails:**

- The accumulator bucket for either invocation contains events from
  the OTHER invocation — would mean the scoping is global rather than
  per-`invocation_id`.
- Both invocations share the same `invocation_id` — would mean the
  per-invocation identity isn't being minted afresh per `invoke()`
  (a §5.1 violation, surfaced via this drain test).
- The drain blocks waiting for events that belong to the other
  invocation — would mean the drain's snapshot set is the global
  pending queue rather than the per-id filtered subset.

**Notes:**

- Serial invocations are sufficient to test the scoping; concurrent
  invocations would test the same rule but introduce harness
  complexity around concurrency that's tangential to the contract
  being verified.
- The fixture pins the per-id scoping rule the resume composition
  (proposal 0039) depends on. When pipeline-utilities resume lands,
  a follow-up fixture under pipeline-utilities/conformance can
  exercise the full resume + drain composition; the spec text in
  §6 *Per-invocation drain* already states the composition rule,
  and this fixture verifies its load-bearing primitive.
