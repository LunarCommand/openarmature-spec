# 009 — Session Migration Chain Ambiguous

Verifies §10's `session_state_migration_chain_ambiguous` category: duplicate `(from, to)` edges
in the registered migration set MUST be rejected at registration time, since the engine has no
deterministic basis to pick one.

**Spec sections exercised:**

- §7 Schema migration — registration-time validation of the migration set.
- §10 Errors — `session_state_migration_chain_ambiguous` is the canonical category for this
  case; mirrors the checkpoint counterpart in pipeline-utilities §10.12.

**Cases:**

1. `duplicate_migration_pair_raises_at_registration` — two distinct migrations for the same
   `(v1, v2)` pair are registered; registration raises before any invoke runs.

**What passes:**

- The error category is `session_state_migration_chain_ambiguous`.
- The error is raised at registration time (compile-time), not at invoke time.
- The error carries the offending `(from_version, to_version)` pair.
- No invoke is attempted.

**What fails:**

- The builder silently drops one of the migrations and proceeds.
- The error surfaces only at invoke time (when a v1 record is actually loaded).
- The error category collapses to a generic configuration error rather than the canonical
  category.
