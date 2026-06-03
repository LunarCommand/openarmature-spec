# 029 — drain_events_for Snapshot Semantic

The set of events covered by a `drain_events_for` call is fixed at the
moment the call begins. Events emitted with the matching
`invocation_id` AFTER the call begins do NOT block the drain. This rule
is load-bearing: without it, every in-node drain would deadlock on the
node's own `completed` event (which fires after the node body — and
the drain call — completes).

**Spec sections exercised:**

- §6 *Per-invocation drain* — snapshot semantic: events covered are
  those emitted with the matching `invocation_id` AND emitted up to
  the moment the call begins. Events emitted after the call do NOT
  block.
- §6 *Per-invocation drain* — the rationale for the snapshot semantic
  (a caller running inside an active invocation would otherwise spin
  indefinitely, because the caller's own node body emits a `completed`
  event AFTER the drain call returns).

**What passes:**

- The drain returns successfully (no deadlock on b's own `completed`
  event).
- The accumulator snapshot at drain return contains a's events and
  b's `started` event, but NOT b's `completed` event — proof that the
  snapshot was taken at call time, not at completion time.
- The final accumulator state (after the invocation fully completes)
  contains b's `completed` event — proof that the deliver loop
  continues processing the queue normally after the drain returns;
  the snapshot semantic only affects which events block the drain,
  not which events eventually deliver.

**What fails:**

- The drain blocks indefinitely (test times out) — would mean the
  snapshot semantic was not implemented; the drain is waiting on b's
  `completed` event which hasn't been emitted yet.
- The accumulator snapshot at drain return contains b's `completed`
  event — would mean the drain blocked until that event was delivered,
  contradicting the snapshot semantic.
- b's `completed` event never appears in the final accumulator state
  — would mean the deliver loop stopped processing the queue after
  drain returned; the drain primitive MUST NOT interfere with normal
  event delivery.

**Notes:**

- This fixture pairs with fixture 028 — 028 verifies the drain
  correctly blocks on PRIOR events; 029 verifies the drain correctly
  does NOT block on SUBSEQUENT events. Together they pin the snapshot
  semantic from both sides.
- The `final_accumulator_state` assertion is taken AFTER the
  invocation completes and after the implicit harness drain — it
  verifies the deliver loop's continued operation after the
  per-invocation drain. Distinguishes from the snapshot taken at the
  moment the drain call returned.
