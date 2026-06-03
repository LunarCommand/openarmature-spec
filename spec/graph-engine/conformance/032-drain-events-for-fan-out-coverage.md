# 032 — drain_events_for Fan-Out Coverage

A fan-out node spawns multiple inner-instance executions that all
share the parent's `invocation_id`. A downstream node after the
fan-out joins calls `drain_events_for(state.invocation_id, ...)` and
reads the accumulator. The snapshot MUST contain events from EVERY
inner instance — not just the most recent — because all instances
share the same `invocation_id` and therefore fall under the same
drain scope.

**Spec sections exercised:**

- §6 *Per-invocation drain* — events scoped via the `invocation_id`
  propagated through the observability §3.4 contextvar mechanism.
  Fan-out inner instances inherit the parent's `invocation_id`.
- §6 *Per-invocation drain* — the per-invocation scope correctly
  handles fan-out without requiring the consumer to enumerate inner
  node names (the load-bearing reason for choosing per-invocation
  scope over per-node scope per proposal 0054's Alternatives §3).

**What passes:**

- The persist node's drain returns with `timeout_reached: false` and
  `undelivered_count: 0`.
- The accumulator snapshot at drain return contains:
  - The fan-out node `process`'s own started + completed pair.
  - 6 inner-instance events (3 instances × 2 phases each).
  - Inner events carry `fan_out_index` values {0, 1, 2} —
    every instance is represented, not just the latest.
  - persist's own started event (per the snapshot semantic;
    started fires before the node body runs).
- The accumulator snapshot does NOT contain persist's completed
  event (fires after the drain call returns).

**What fails:**

- Inner events from some fan-out instances are missing — would mean
  the drain only covered a subset of inner instances (e.g., per-node
  scoping rather than per-invocation).
- The `inner_fan_out_indices_seen` set is incomplete (missing 0, 1,
  or 2) — same as above; would mean per-instance scoping is broken.
- persist's completed event is in the snapshot — would mean the
  snapshot semantic was not honored (the drain blocked on persist's
  own completed event, which would deadlock in general).

**Notes:**

- This fixture is the canonical end-of-fan-out consumer pattern:
  a downstream "persist" or "summary" node that needs to aggregate
  data accumulated across every inner instance before writing a
  canonical record. Without per-invocation drain, this consumer
  has no way to synchronize on the dispatch tail of inner-instance
  events — the race the primitive resolves.
- Locks down the per-invocation scoping rationale from proposal
  0054 §3 Alternatives: the per-node-scope alternative was rejected
  because a downstream-of-fan-out consumer would need to enumerate
  every inner node name. Per-invocation scope handles it
  transparently because all inner instances share the parent's
  `invocation_id`.
