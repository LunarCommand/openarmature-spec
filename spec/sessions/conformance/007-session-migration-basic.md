# 007 — Session Schema Migration (Basic)

Verifies §7 schema migration: a registered `(from_version, to_version)` migration runs at load
time between `SessionStore.load()` and the §4 projection merge. The migrated state is what the
graph sees; the engine writes the new schema version on save.

**Spec sections exercised:**

- §7 Schema migration — load → migrate → merge → run → save sequencing.
- §4 Session shape and projection — migration runs in the record's dict form, before the
  projection's inbound merge.
- §10 Errors — `session_state_migration_missing` is NOT raised when a path is registered (see
  fixture 008 for the missing case).

**Cases:**

1. `registered_migration_applies_at_load` — store seeded with a v1 record `{value: 1}`; v1 → v2
   migration adds 10; the graph runs against `{value: 11}` and saves at v2.

**What passes:**

- The migration runs exactly once.
- The graph's pre-execution state is `{value: 11}` (post-migration), not `{value: 1}` (raw v1).
- The saved record after END has `schema_version="v2"` and `state={value: 11}`.

**What fails:**

- The graph runs against `{value: 1}` (migration was skipped or ran after the merge).
- The migration runs more than once.
- The saved record retains `schema_version="v1"` (the new version wasn't written on save).
