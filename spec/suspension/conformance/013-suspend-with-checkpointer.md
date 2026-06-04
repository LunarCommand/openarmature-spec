# 013 — Suspend with checkpointer backend

The paused-invocation record persists via the same persistence
machinery as checkpoint records (pipeline-utilities §10.15). The
record type discriminator (or separate-stores choice) ensures the
record is treated as suspended, not as a checkpoint.

**Spec sections exercised:**

- §8.5 — checkpointing composition: shared persistence mechanism;
  distinct record types.
- pipeline-utilities §10.15 — composition with suspension rule;
  record-type distinction; paused-record lifetime not bound to
  invocation completion.

**What passes:**

- After suspend, the configured backend has a paused-invocation
  record with `record_type = "suspended"`.
- Resume via the suspension API (`signal_payload` present) succeeds
  and completes the graph.

**What fails:**

- No paused-invocation record exists after suspend — would mean the
  suspension's persistence path did not use the configured
  checkpointer backend.
- The record is stored as a checkpoint (not as a suspended record) —
  would mean the record-type discriminator is missing.
