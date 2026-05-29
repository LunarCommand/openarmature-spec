# 013 — Session Migration Function Raises

Verifies §10's `session_state_migration_failed` category: when a registered migration function
itself raises during chain application, the engine MUST surface the failure with that category
(carrying the offending `(from, to)` pair and preserving the raised exception as cause), rather
than routing to a generic load error or to the `_missing` category.

**Spec sections exercised:**

- §7 Schema migration — a migration-function failure has its own dedicated category, distinct
  from "no path registered."
- §10 Errors — `session_state_migration_failed` mirrors `checkpoint_state_migration_failed`
  (pipeline-utilities §10.12). The graph MUST NOT run when migration fails mid-chain.

**Cases:**

1. `buggy_migration_routes_to_failed_category` — registered v1 → v2 migration raises KeyError;
   engine raises `session_state_migration_failed`; graph never runs.

**What passes:**

- The error category is `session_state_migration_failed`.
- The error carries `from_version="v1"` and `to_version="v2"`.
- The error preserves the raised `KeyError` as its cause.
- The graph's entry node is never invoked.

**What fails:**

- The engine routes the failure to `session_load_failed` (treating it as a generic load error).
- The engine routes to `session_state_migration_missing` (the path WAS registered; the function
  ran and raised — that's a distinct category).
- The original exception is dropped (no `cause` is attached to the surfaced error).
- Subsequent migrations in the chain are attempted after the failing one.
