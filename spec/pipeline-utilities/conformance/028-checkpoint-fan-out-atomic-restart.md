# 028 — Fan-Out Atomic Restart In v1

Verifies §10.7 atomic-restart fan-out resume behavior in v1, plus §10.3's "no fan-out
internal saves" rule. A fan-out aborts mid-execution; the saved record does NOT contain
any per-instance progress (no fan-out internal saves were ever produced); on resume, the
entire fan-out re-runs from scratch including instances that previously completed and
merged.

The "no internal saves" rule is the load-bearing assertion. v1 atomic-restart could in
principle work by saving fan-out internals and ignoring them on resume, but the spec
chooses to elide those saves entirely so that the runtime cost of fan-out checkpointing
matches the resume capability — neither over-pays nor under-saves.

A follow-on proposal will add per-instance fan-out resume, which reverses both the elision
and the atomic-restart contract.

**Spec sections exercised:**

- §10.7 Fan-out resume — atomic in v1; the entire fan-out re-runs on resume.
- §10.3 Save granularity — fan-out instance internal `completed` events do NOT trigger saves.
- §10.2 Checkpoint record shape — `fan_out_progress` is reserved and absent in v1.

**Cases:**

1. `fan_out_aborts_in_instance_2_resume_re_runs_all_three` — 3-instance fan-out with
   `error_policy: fail_fast`; instance 2 fails on first run; instances 0 and 1 had completed
   internally (visible via §6 observer events) but their completion did NOT save (per
   §10.3); on resume, all 3 instances re-dispatch.

**What passes:**

- The saved record contains no fan-out internal `completed_positions`.
- The saved record's `fan_out_progress` is absent or null.
- The fan-out node itself is not in `completed_positions` (it never completed as a unit).
- On resume, all 3 instances re-execute (the harness allows them all to succeed); final
  `results == [10, 20, 30]`.

**What fails:**

- The saved record contains per-instance `completed_positions` (would mean §10.3's elision
  is not honored).
- The saved record contains a populated `fan_out_progress` (v2 behavior leaked into v1).
- On resume, the engine attempts to skip instances 0 and 1 (would require consulting state
  that v1 explicitly does not save).
