# 052 — Checkpoint Fan-Out Collect Errors Resume

Verifies §10.11.2's `collect` composition. Under `error_policy:
collect`, failed instances contribute error entries to the accumulator's
`errors_field` bucket; those error contributions are first-class
`completed` contributions under §10.11. On resume, they are preserved
and rolled forward — NOT re-recorded.

**Spec sections exercised:**

- §10.11.2 `collect` composition — error contributions are
  checkpointable `completed` entries.
- §10.11 `fan_out_progress.result` field can carry either a success
  value or an error entry depending on `error_policy`.
- §10.7 Per-instance resume — `completed` instances (whether
  success-recorded or error-recorded) skip on resume.

**What passes:**

- Saved record has instances 0 and 1 as `completed` with success
  results, instance 2 as `completed` with an error result.
- Resume skips all three; runs only instances 3 and 4.
- Final `results` has 4 success entries (`[10, 20, 30, 40]`); `errors`
  has exactly 1 entry (instance 2's failure from the first run).

**What fails:**

- Resume re-runs instance 2 — would mean error-mode `completed` was
  being treated differently from success-mode `completed`, contradicting
  the §10.11.2 path-agnostic rule.
- `errors` list has 2 entries on resume — would mean instance 2's
  error was both preserved AND re-recorded.
- `errors` list is empty after resume — would mean instance 2's saved
  contribution was not preserved.

**Notes:**

- The `abort_after_instance: 2` harness directive simulates a
  process-level crash that fires between instance 2's completion-save
  and instance 3's dispatch. Distinct from fail_fast (which would not
  abort under collect mode) and from a node-level exception inside an
  instance (which collect mode would capture as an error entry, not an
  abort).
- The `result_kind: error` assertion accommodates the
  implementation-defined representation of error contributions in the
  saved record. Implementations MAY represent error contributions as
  structured records, error class instances, serialized exception
  metadata, etc.; the harness checks only that the result is an error
  kind, not its specific shape.
