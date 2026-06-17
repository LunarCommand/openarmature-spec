# 070 — crash_injection `after_node` resume

Pins the `crash_injection.after_node` boundary (conformance-adapter §5.6) — fixture 067 exercises
only `after_fan_out_instance`. Unlike a node failure, `after_node` crashes the run *after* a
regular node's checkpoint save has fired, leaving only the checkpoint; on resume the node rolls
forward (it is in `completed_positions`, not re-run) and the downstream nodes execute. This is the
resume-from-completed-position behavior of fixture 025, reached via `crash_injection` instead of a
node raise.

**Spec sections exercised:**

- conformance-adapter §5.6 — `crash_injection: {after_node: <node>}` (crash on the node's `completed`
  save, no failure) + `resume` from the saved checkpoint.
- pipeline-utilities §10.3 / §10.4 — `completed_positions` and the resume model (skip completed
  nodes, run the rest; fresh `invocation_id`, preserved `correlation_id`).

**Case `crash_after_node_a_resume_skips_a`:**

- Three nodes A → B → C under an in-memory checkpointer; `crash_injection: {after_node: node_a}`.
- Saved record: `node_a` in `completed_positions`, state `{a_ran: true, b_ran: false, c_ran: false}`.
- Resume: `node_a` skipped, `node_b` + `node_c` run; final state `{a_ran, b_ran, c_ran} = true`.

**What passes:**

- The crash lands after `node_a`'s save; the saved record carries `node_a` in `completed_positions`.
- On resume `node_a` is not re-run; `node_b` and `node_c` execute; final state matches an
  uninterrupted run.
- The resumed invocation has a fresh `invocation_id` with the original `correlation_id` preserved.

**What fails:**

- `node_a` re-runs on resume (not recognized as a completed position) — the `after_node` boundary
  didn't persist `node_a` as completed.
- The crash fires before `node_a`'s save (empty `completed_positions`) — wrong boundary.
- Downstream nodes don't run on resume, or final state diverges from an uninterrupted run.
