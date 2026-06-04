# 001 — Basic suspend/resume cycle

The canonical suspension flow: a node calls `suspend(descriptor)` with
the default `mark_node_completed=True`; `invoke()` returns a suspended
outcome carrying the descriptor; a follow-up `invoke()` with
`resume_invocation` and `signal_payload` loads the paused record,
merges the payload into state, and continues from the node AFTER the
suspending node.

**Spec sections exercised:**

- §3 — `suspend(descriptor, mark_node_completed=True)` is the node's
  terminal action; engine persists state and returns suspended outcome.
- §5 — suspended outcome shape: `outcome="suspended"`, `descriptor`,
  `node_name`.
- §6 — shallow field overlay merge of `signal_payload` into loaded
  state.
- §7 — resume API: load paused record, merge payload, continue at
  next node (since suspending node IS in `completed_positions` under
  the default).

**What passes:**

- Initial invoke returns suspended outcome with
  `descriptor.signal_id == "approval-12345"` and
  `descriptor.metadata.kind == "approval"`.
- Resume invoke runs `next_node` (the gate node is NOT re-run).
- Final state has `approved=true` (from signal payload) and
  `completed_flag=true` (from next_node's update).

**What fails:**

- Initial invoke returns completed or errored — would mean suspend
  was not recognized as a terminal action.
- Resume invoke re-runs the gate node — would mean
  `mark_node_completed=True` was not honored.
- Final state's `approved` is `false` — would mean the signal_payload
  merge did not apply.
