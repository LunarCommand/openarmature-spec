# 033 — Parallel Branches Fail-Fast

Three branches; the second (`beta`) raises after the first (`alpha`) has
already completed; the third (`gamma`) is mid-flight (slow inner node).
Verifies the §11.5 fail_fast contract — first failure cancels still-running
branches, no contributions land in parent state.

**Spec sections exercised:**

- §11.4 Per-branch projection (out) — buffered-then-applied semantics:
  alpha's successful contribution is held in the buffer, never applied.
- §11.5 Error policy — fail_fast cancels gamma; raises
  `parallel_branches_branch_failed` wrapping beta's exception.
- The §11.4 + §11.5 interaction: `recoverable_state` is the pre-entry parent
  snapshot, NOT the snapshot with alpha's contribution applied.

**What passes:**

- The graph raises `parallel_branches_branch_failed` with `branch_name=beta`
  and the cause carrying beta's `"branch beta failed"` message.
- `recoverable_state` shows ALL parent fields at their initial defaults
  (alpha's contribution buffered then discarded; gamma never completed).

**What fails:**

- `recoverable_state` shows alpha's contribution applied (`alpha_result: 1`)
  — would mean the engine applied per-branch contributions incrementally,
  contradicting §11.4 collect-then-apply.
- `recoverable_state` shows gamma's contribution applied (`gamma_result: 3`)
  — would mean cancellation didn't happen.
- A different error category is raised (e.g., `node_exception` without the
  parallel-branches wrapping).
