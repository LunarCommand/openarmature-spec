# 069 — Fan-out degrade contribution refinements

Verifies proposal 0069's three §9.3 refinements to 0066's fan-out
degrade-contribution model: an omitted `extra_outputs` source is a positional
**null slot** (not "not contributed"); an absent `collect_field` on any fan-in
path is a graceful **null slot** that never raises; and a degraded instance's
slot survives a checkpoint + resume round-trip.

**Spec sections exercised:** pipeline-utilities §9.3 (degrade contribution —
`extra_outputs` null slot, absent-`collect_field` gracefulness), §9.4
(instance-index ordering), §10.11 (per-instance fan-out resume). Uses
conformance-adapter §5.6 `crash_injection` (proposal 0070) for the resume case.

**Cases:**

1. `extra_outputs_omission_is_null_slot` — a single-instance fan-out with
   `failure_isolation` whose `degraded_update` supplies `collect_field` (`out`)
   but omits the `extra_outputs` source (`note`). Asserts the mapped parent
   field holds **`null` at the instance's slot** (`notes: [null]`),
   index-aligned with `target_field` — not absent or a shortened list.
2. `absent_collect_field_yields_null_slot_no_raise` — a callable
   `degraded_update` that sets only `note`, omitting `collect_field` (`out`).
   Asserts the `results` slot is `null` and the fan-in does **not** raise
   (re-affirming §9.8 from the §9.3 generalization: an absent `collect_field`
   on any path is a graceful null, never a `fail_fast`-stopping raise).
3. `degrade_slot_survives_resume` — the degraded instance completes, then
   `crash_injection: {after_fan_out_instance: {node: process, index: 0}}` ends
   the first run after its completion save. On resume the degraded slot
   (`results: ["(degraded)"]`, the null `notes` slot) rolls forward unchanged;
   instance 0 is skipped, nothing re-runs.

**What passes:**

- An omitted `extra_outputs` source contributes `null` at the positional slot.
- An absent `collect_field` (callable degrade omitting it) yields a null slot
  and the fan-in does not raise.
- A degraded instance's recorded slot is preserved across resume (not
  recomputed or dropped).

**What fails:**

- Shortening the `extra_outputs` list (dropping the omitted slot), misaligning
  it from `target_field`.
- Raising at fan-in on an absent `collect_field` (stopping the graph under
  `fail_fast`).
- Re-running or dropping the degraded instance on resume.

**Relationship to fixture 065 (0066):** 065 pins the supplied-value degrade
contribution and the static-omission compile error; 069 refines the *omission*
shape (`extra_outputs` → null slot) and adds the resume round-trip, neither of
which 065 exercises.
