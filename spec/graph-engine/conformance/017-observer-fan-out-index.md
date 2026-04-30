# 017 — Observer Fan-Out Index

Verifies the §6 `fan_out_index` field added by proposal 0005: per-instance events from a fan-out
carry `fan_out_index` matching the instance index on BOTH started and completed phases. The
fan-out node's own pair has `fan_out_index` absent. Events from nodes outside the fan-out (here:
`pre`) also have `fan_out_index` absent.

The combination of `namespace`, `fan_out_index`, `attempt_index`, and `phase` uniquely identifies
each event source.

**Spec sections exercised:**

- §6 `fan_out_index` field — populated only inside fan-out instances.
- §6 pair model — every attempt produces started + completed.
- §6 identity rule — `namespace` + `fan_out_index` + `attempt_index` + `phase` is unique per event
  source.
- pipeline-utilities §9 — fan-out node fires its own pair with `fan_out_index` absent (the
  fan-out node itself is at the parent level, not inside any fan-out instance).

**What passes:**

- Pre-node `pre` produces 2 events (one started, one completed); both have `fan_out_index`
  absent.
- Fan-out node `process` produces 2 events (one started, one completed); both have
  `fan_out_index` absent (the fan-out itself is a parent-level node).
- Inner-instance events: 6 total (3 instances × 2 phases). Each carries `fan_out_index` matching
  its instance index (0/1/2) and `attempt_index == 0` (no retry middleware).

**What fails:**

- Inner events lack `fan_out_index`.
- Fan-out node's own events have `fan_out_index` populated (it shouldn't — the fan-out is at the
  parent level).
- Events outside the fan-out have `fan_out_index` populated.
- Pair model not honored (only one event per attempt, missing `phase`).
