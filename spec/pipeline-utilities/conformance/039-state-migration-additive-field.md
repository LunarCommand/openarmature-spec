# 039 — State Migration Additive Field

Smallest possible state migration: a saved record at `schema_version="v1"`
carries a state that lacks an optional field added in `v2`; a single
registered `v1 -> v2` migration populates the new field with its default.
Resume succeeds with the migrated state.

**Spec sections exercised:**

- §10.2 (post-proposal-0014) — `schema_version` as a user-facing identifier
  on the state schema.
- §10.12.1 Migration registration — one migration registered on the
  compiled graph.
- §10.12.2 Chain resolution — single-edge chain (`v1 -> v2`) applied at
  load time before deserialization.

**What passes:**

- The migration runs exactly once.
- Final state has `new_field == "v2_default"` and `x == 7` (preserved from
  the seeded v1 state).
- The resumed invocation completes normally.

**What fails:**

- The migration runs more than once (would mean the engine re-applied it).
- `new_field` absent from final state (would mean the migration's output
  didn't reach the v2 state class).
- The resumed invocation raises `checkpoint_state_migration_missing`
  (would mean the migration wasn't consulted).
- `x` corrupted or lost (would mean the migration mishandled untouched
  fields).
