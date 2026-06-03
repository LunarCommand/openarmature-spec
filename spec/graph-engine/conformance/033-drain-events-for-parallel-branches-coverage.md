# 033 — drain_events_for Parallel-Branches Coverage

Peer fixture to 032 (fan-out coverage). A parallel-branches dispatcher
fires multiple named branches concurrently; all branches share the
parent's `invocation_id`. A downstream node after the dispatcher joins
calls `drain_events_for(state.invocation_id, ...)` and reads the
accumulator. The snapshot MUST contain events from EVERY branch.

The two concurrent-dispatch primitives — fan-out (§3 / proposal 0005)
and parallel-branches (§3 / proposal 0011) — exercise different engine
code paths but share the same `invocation_id` scoping contract for
observer events. Both fixtures together lock down per-invocation drain
coverage of all events regardless of which dispatch shape produced
them.

**Spec sections exercised:**

- §6 *Per-invocation drain* — events scoped via the `invocation_id`
  defined in observability §5.1. Parallel-branches inner branches
  inherit the parent's `invocation_id` (the default for non-detached
  inner subgraphs).
- §6 *Per-invocation drain* — the per-invocation scope correctly
  handles parallel-branches without requiring the consumer to
  enumerate branch names. Parallel coverage to fixture 032's fan-out
  rationale.

**What passes:**

- The persist node's drain returns with `timeout_reached: false` and
  `undelivered_count: 0`.
- The accumulator snapshot at drain return contains:
  - The `dispatcher` node's own started + completed pair.
  - 4 inner-branch events (2 branches × 2 phases each).
  - Inner events carry `branch_name` values {alpha, beta} — both
    branches are represented.
  - `persist`'s own started event (per the snapshot semantic;
    started fires before the node body runs).
- The accumulator snapshot does NOT contain `persist`'s completed
  event (fires after the drain call returns).

**What fails:**

- Inner events from one branch are missing — would mean the drain
  only covered a subset of branches (e.g., per-node scoping rather
  than per-invocation, or the implementation tags fan-out events with
  invocation_id but misses parallel-branches events).
- `inner_branch_names_seen` is incomplete (missing alpha or beta) —
  same as above; the branch-event tagging is incomplete.
- `persist`'s completed event is in the snapshot — would mean the
  snapshot semantic was not honored.

**Notes:**

- This fixture is the parallel-branches peer to fixture 032's
  fan-out case. Without it, an implementation could correctly tag
  fan-out instance events with the parent's `invocation_id` and
  silently break parallel-branches' tagging (the two dispatch shapes
  emit events via different engine code paths even though they share
  the same observability contract).
- The fan-out + parallel-branches pair is the complete coverage of
  the engine's concurrent-dispatch surface for per-invocation drain.
  Future concurrent-dispatch primitives (if any) would warrant
  similar fixture coverage.
