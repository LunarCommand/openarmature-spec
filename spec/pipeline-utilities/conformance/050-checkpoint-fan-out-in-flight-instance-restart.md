# 050 — Checkpoint Fan-Out In-Flight Instance Restart

Verifies §10.7's "in-flight instance restarts from its entry point"
rule. The `completed_inner_positions` field on an `in_flight`
fan_out_progress entry is observational (what the inner subgraph had
done at save time), NOT a resume point. The inner subgraph re-enters at
its declared entry on resume; the §10.5 idempotency contract makes this
safe.

**Spec sections exercised:**

- §10.7 Per-instance resume — `in_flight` state behavior on resume.
- §10.11 `fan_out_progress.instances[].completed_inner_positions` —
  shape for `in_flight` entries; observable but not state-restore.
- §10.5 Idempotency contract — re-running inner nodes is safe under
  the user's idempotency discipline.

**What passes:**

- Saved record has instance 1 with `state: in_flight` AND
  `completed_inner_positions: [{node_name: step_a, ...}]` (capturing
  that step_a had completed before the abort).
- On resume, instance 1 re-runs both step_a AND step_b — the
  subgraph re-enters at its declared entry (step_a), not at step_b.
- Final state is correct.

**What fails:**

- On resume, instance 1 skips step_a and runs only step_b — would
  mean `completed_inner_positions` was being treated as a
  state-restore point inside the subgraph (NOT the spec contract).
- The saved record's `completed_inner_positions` is empty or missing
  for instance 1 — would mean the harness didn't capture the inner
  save granularity per §10.3.

**Notes:**

- This fixture demonstrates the deliberate scope cut in §10.7: per-
  instance resume restarts the *instance* (treats it as an atomic
  unit), not the inner nodes within. Per-inner-node resume *inside* a
  fan-out instance would require a different contract (and would
  significantly complicate the reducer-interaction story in §10.11.1).
- The capture of `completed_inner_positions` is opportunistic — it
  fires only when a sibling instance's completion triggers a save
  during this instance's execution. If no sibling completes before the
  crash, the saved record either doesn't exist or pre-dates fan-out
  dispatch entirely (all instances `not_started`).
