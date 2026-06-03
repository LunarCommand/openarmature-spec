# 028 — drain_events_for Basic Synchronization

The canonical use case for the per-invocation drain primitive: an
accumulating observer records events into a per-`(invocation_id)` bucket
as they are delivered; a terminal node calls
`drain_events_for(state.invocation_id, ...)` and then reads the
accumulator. After the drain returns, the accumulator MUST contain
every event the prior nodes emitted.

**Spec sections exercised:**

- §6 *Observer hooks* — `drain_events_for(invocation_id, *, timeout)`
  exists as a sibling to the process-wide `drain`.
- §6 *Per-invocation drain* — the snapshotted set of events MUST be
  delivered to every registered observer before the drain returns.
- §6 *Per-invocation drain* — `undelivered_count == 0` and
  `timeout_reached == false` on the idempotent / already-drained
  path (or after the drain successfully completes).

**What passes:**

- The drain returns with `timeout_reached == false` and
  `undelivered_count == 0`.
- The accumulator's per-invocation bucket at drain return contains
  every event emitted before the drain call (a's started + completed
  pair, plus b's own started event — b's `completed` event has not yet
  fired at the moment of the drain call, per the snapshot semantic).

**What fails:**

- The accumulator at drain return is missing the prior node's
  `completed` event — would mean the drain returned before that event
  was delivered (race not closed).
- The accumulator at drain return contains b's `completed` event —
  would mean the snapshot semantic is broken (the drain covered events
  emitted after the call begin, which would create an infinite wait in
  general).
- The drain summary reports a non-zero `undelivered_count` — would mean
  the snapshot was not fully delivered when drain returned.

**Notes:**

- The `sleep_ms_per_event: 50` setting on the accumulator creates a
  non-trivial dispatch tail; without `drain_events_for`, a fast
  terminal node could read the accumulator before the prior node's
  `completed` event has been dispatched.
- The harness primitive `invoke_drain_events_for` on a node spec
  means: from inside that node's body, invoke
  `drain_events_for(state.invocation_id, timeout=...)`, then capture
  the named observer's accumulator bucket for that invocation_id.
  Both the drain summary and the snapshot are exposed under the
  node's name in the expected section.
