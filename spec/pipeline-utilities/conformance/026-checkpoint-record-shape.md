# 026 — Checkpoint Record Shape

Verifies §10.2: the saved `CheckpointRecord` carries every required field with well-formed
values. `fan_out_progress` is reserved for the v2 per-instance fan-out resume follow-on; in
v1 it is absent (this fixture's graph has no fan-out, so the field's reserved status is
verified directly).

**Spec sections exercised:**

- §10.2 Checkpoint record shape — `invocation_id`, `correlation_id`, `state`,
  `completed_positions`, `parent_states`, `last_saved_at`, `schema_version` (all required);
  `fan_out_progress` (reserved, absent in v1).
- §10.4 step 3 — `correlation_id` matches the caller-supplied value.
- Observability §5.1 — `invocation_id` is a UUIDv4.

**Cases:**

1. `record_carries_required_fields` — two-node linear graph with a caller-supplied
   `correlation_id`; assert the latest saved record carries all required fields with valid
   values.

**What passes:**

- `invocation_id` is a canonical UUIDv4.
- `correlation_id` matches the caller-supplied string verbatim.
- `state` matches the final post-merge outermost state.
- `completed_positions` lists every completed node attempt in step order.
- `parent_states` is an empty list (no subgraph or fan-out nesting).
- `fan_out_progress` is absent or null (reserved field, no fan-out in this case).
- `last_saved_at` is present and monotonic across the run's saves.
- `schema_version` is present (any string).

**What fails:**

- Any required field missing or malformed.
- `invocation_id` is a counter or non-UUIDv4.
- `correlation_id` is transformed (prefixed, hashed, truncated) instead of used verbatim.
- `parent_states` is null instead of empty list at the outermost graph (the field is always
  present; the value is empty when there is no nesting).
- `fan_out_progress` is populated (no fan-out exists in this fixture, so v1 must NOT produce
  it).
