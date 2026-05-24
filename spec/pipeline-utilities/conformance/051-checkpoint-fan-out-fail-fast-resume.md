# 051 — Checkpoint Fan-Out Fail-Fast Resume

Verifies §10.11.2's `fail_fast` composition. Under `error_policy:
fail_fast`, a failed instance cancels siblings; the fan-out raises. On
resume, instances that completed-and-recorded before the failure are
skipped (their `result` entries roll forward); failed and cancelled
instances re-run.

**Spec sections exercised:**

- §10.11.2 `fail_fast` composition — pre-failure completed instances
  retain `completed` status; failed instance is `in_flight`;
  cancelled-or-not-dispatched siblings are `in_flight` or
  `not_started`.
- §10.7 Per-instance resume — skip / re-run / dispatch by per-instance
  state.
- §10.6 Retry on resume — `attempt_index` resets to 0 on resume.

**What passes:**

- Saved record has instance 0 as `completed` with `result: 10`,
  instance 1 as `in_flight`, instance 3 as `not_started`; instance 2
  is one of `in_flight` / `not_started` depending on execution mode
  (serial vs concurrent).
- Resume skips instance 0; re-runs instances 1, 2, 3.
- Final `results` list is `[10, 20, 30, 40]` — instance 0's saved
  contribution is preserved; instances 1-3 contribute on resume.

**What fails:**

- Instance 0 re-runs on resume — would mean fail-fast cancellation
  invalidated already-completed instances, contradicting §10.11.2.
- Final `results` is `[10, 10, 20, 30, 40]` (double-counted) — would
  mean instance 0's saved entry was preserved AND the instance re-ran,
  violating the §10.11.1 reducer-interaction guarantee.
- Instance 1's `attempt_index` on resume is not 0 — would mean the
  retry budget persisted across resume in violation of §10.6.

**Notes:**

- `state_one_of: [in_flight, not_started]` on the instance 2 assertion
  accommodates both serial and concurrent execution modes. Under
  serial, instance 2 never dispatched (instance 1 failed first); under
  concurrent, instance 2 may have been in-flight when fail_fast
  cancelled it.
- Distinct from 052 (collect mode), where the fan-out runs to
  completion despite individual failures and `result` entries on
  `errors_field` are themselves checkpointable.
