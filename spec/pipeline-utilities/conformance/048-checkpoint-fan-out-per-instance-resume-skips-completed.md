# 048 — Checkpoint Fan-Out Per-Instance Resume Skips Completed

The foundational fixture for per-instance fan-out resume (§10.7, §10.11).
Verifies that on resume into an aborted fan-out, instances whose
`completed` state was durably recorded in the saved record's
`fan_out_progress` are skipped — their accumulator entries roll forward
to the fan-in step rather than being recomputed.

**Spec sections exercised:**

- §10.7 Per-instance fan-out resume — `completed`/`in_flight`/`not_started`
  classification and resume behavior.
- §10.11 `fan_out_progress` semantics — the per-instance status with
  `result` field for `completed` entries.
- §10.3 Save granularity — fan-out instance internal saves now fire
  (the v1 "engine does NOT save" elision is removed).

**What passes:**

- The first run aborts at instance 3 with `node_exception`.
- The saved record's `fan_out_progress` shows instances 0, 1, 2 as
  `completed` with `result` populated; instance 3 as `in_flight`;
  instance 4 as `not_started`.
- Resume executes ONLY instances 3 and 4 (no `started` events for
  0, 1, 2).
- Final `results` list is `[10, 20, 30, 40, 50]` — one entry per
  instance, in instance-index order, with no duplicates.

**What fails:**

- Resume re-runs instances 0, 1, 2 (atomic-restart behavior) — would
  mean per-instance resume is not implemented.
- Resume runs only instance 4 (skipping instance 3) — would mean
  `in_flight` is being treated as `completed`, violating the §10.11
  atomicity contract.
- Final `results` has duplicate entries (e.g., `[10, 10, 20, 20, ...]`)
  — would mean completed instances are double-merging via the reducer.

**Notes:**

- `concurrent_mode: serial` is used to make the per-index completion
  order deterministic; per-instance resume's correctness does not depend
  on serial execution, but the fixture's saved-record assertions do.
- This is the foundational case; fixture 049 specifically stresses the
  `append` reducer's no-double-merge correctness with stricter
  assertions on the merged list.
