# 067 — crash_injection fan-out resume

Verifies proposal 0070's `crash_injection` directive (conformance-adapter
§5.6): a resume can be triggered at a checkpoint boundary **without** an
instance failure, so resume is testable from any saved state — here, a fan-out
where an instance completed normally.

**Spec sections exercised:** conformance-adapter §5.6 (`crash_injection`,
`resume`) and §5.8 (`saved_record_assertions`,
`instances_executed/skipped_during_resume`); pipeline-utilities §10.11
(per-instance fan-out resume).

**Case:**

1. `crash_after_instance_0_resume_rolls_forward` — a 2-instance fan-out
   (`[10, 20]`, serial). Instance 0 completes and records its contribution;
   `crash_injection: {after_fan_out_instance: {node: process, index: 0}}` ends
   the first run with **no** error immediately after instance 0's completion
   save. The saved record shows instance 0 `completed`, instance 1
   `not_started`. On resume, instance 0 is skipped and instance 1 runs; final
   `results` is `[10, 20]`.

**What passes:**

- `crash_injection` ends the first run after the named instance's completion
  save, with no asserted first-run outcome; only the checkpoint persists.
- The saved `fan_out_progress` records the completed and not-started instances.
- On resume, the completed instance is skipped (rolled forward) and the
  remaining instance executes, with no duplicate accumulator entries.

**What fails:**

- Re-running the completed instance on resume (it must be skipped).
- Requiring an instance failure to reach the resume — the point of
  `crash_injection` is failure-independent resume-from-any-state.
