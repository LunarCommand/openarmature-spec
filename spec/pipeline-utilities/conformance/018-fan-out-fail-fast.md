# 018 — Fan-Out Fail-Fast

Verifies §9.5 default `error_policy: "fail_fast"` semantics: one instance raises, siblings cancel,
fan-out node propagates `node_exception` per graph-engine §4 with `recoverable_state` at the
pre-fan-out snapshot.

**Spec sections exercised:**

- §9.5 fail_fast policy — first raise cancels siblings, propagates a single node_exception.
- §9.5 cancellations are infrastructure (not user-visible errors).
- graph-engine §4 — `node_exception` carries `recoverable_state` (the pre-merge state at fan-out
  entry, NOT post-merge — fan-out's contributions never merged).

**What passes:**

- Engine raises `node_exception` from `process`.
- `recoverable_state == {items: [0, 1, 2], results: []}` — items unchanged, results empty (the
  fan-out's contributions never merged).
- Sibling instances (idx 0 and 2) were cancelled. Their final-state events do NOT fire as
  `post_state`-populated `completed` events; whatever fired before cancellation propagated may
  surface as `started` events with no matching `completed`, or `completed` with cancellation
  marker (Python `CancelledError`).

**What fails:**

- The fan-out doesn't raise (engine swallowed the failure or merged partial results).
- `recoverable_state` reflects post-fan-out partial merging.
- Sibling instances continue to completion despite the early failure.
