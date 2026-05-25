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
- Final `results` has 4 success entries (`[10, 20, 40, 50]` — instances
  0, 1, 3, 4); `errors` has exactly 1 entry (instance 2's failure from
  the first run).

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
- The `result_is_error: true` assertion on instance 2 is the normative
  discrimination mechanism per §10.11: implementations MUST populate
  this boolean field on every per-instance entry and consult it on
  resume to route the rolled-forward contribution
  (`true` → `errors_field`, `false` → `target_field`). The companion
  `result_present: true` matcher asserts that the `result` field exists
  on the saved record without constraining its shape — §10.11 mandates
  that `completed` entries MUST reflect their contribution in `result`,
  but the error-record shape itself remains implementation-defined per
  §9.5 (implementations MAY represent error contributions as structured
  records, error class instances, serialized exception metadata, etc.).
  The harness checks the existence and the boolean discriminator, not
  the specific representation.
