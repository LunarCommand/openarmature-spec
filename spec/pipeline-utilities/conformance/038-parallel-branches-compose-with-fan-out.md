# 038 — Parallel Branches Composition With Fan-Out

Two branches; one (`with_fan_out`) contains a fan-out node in its subgraph,
the other (`plain`) is a flat subgraph. Verifies §11 + §9 composition and
the graph-engine §6 invariant that `branch_name` and `fan_out_index` are
independent and MAY both be populated on the same event.

**Spec sections exercised:**

- §11.6 / §11 cross-spec — parallel branches and fan-out compose
  without interference.
- graph-engine §6 — the §6 `NodeEvent.branch_name` and
  `NodeEvent.fan_out_index` fields are populated independently;
  inner-node events from inside a fan-out inside a parallel-branches
  branch carry BOTH fields.
- §9 fan-out, §11 parallel branches — each operates per its own contract;
  their concurrency exceptions (graph-engine §3) stack.

**What passes:**

- Final `fan_out_scores == [20, 40, 60]` — the fan-out inside the
  `with_fan_out` branch produced doubled values in input order.
- Final `plain_value == 100`.
- Observer events from the fan-out's inner `compute` node carry
  `branch_name="with_fan_out"` AND `fan_out_index` in `{0, 1, 2}`.
- Observer events from the plain branch's inner `v` node carry
  `branch_name="plain"` and no `fan_out_index`.

**What fails:**

- `branch_name` absent on fan-out inner events (would mean §11.6 isn't
  propagating `branch_name` through composed subgraphs).
- `fan_out_index` absent on fan-out inner events when `branch_name` is
  present (would mean the engine treated the fields as mutually exclusive,
  violating §6's independence invariant).
- `fan_out_scores` not in input order — fan-out's own §9.4 contract
  violated by the parallel-branches composition.
