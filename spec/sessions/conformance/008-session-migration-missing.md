# 008 — Session Schema Migration Missing

Verifies §10's `session_state_migration_missing` category: when the loaded record's
`schema_version` differs from the current graph's expected version and NO migration chain is
registered, the engine MUST raise (carrying the offending `(from, to)` pair) rather than load the
raw record.

**Spec sections exercised:**

- §7 Schema migration — migration is required when versions differ.
- §10 Errors — `session_state_migration_missing` is the canonical category for this case;
  non-transient.

**Cases:**

1. `missing_migration_raises_at_load` — store seeded with a v1 record; graph at v2; no migrations
   registered. The engine raises before the graph runs.

**What passes:**

- The engine raises `session_state_migration_missing` carrying `from_version="v1"` and
  `to_version="v2"`.
- The graph's entry node is never invoked.
- The store's record is unchanged after the failed load.

**What fails:**

- The engine loads the v1 state into a v2 graph (silent data corruption).
- A different error category is raised (e.g., `session_load_failed` or a generic validation
  error).
- The error does not carry the offending version pair.
