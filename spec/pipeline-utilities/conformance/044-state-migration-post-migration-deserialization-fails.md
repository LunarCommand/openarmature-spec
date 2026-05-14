# 044 — State Migration Post-Migration Deserialization Failure

A registered `v1 -> v2` migration runs successfully but its output does
NOT match the current `v2` state class's deserialization contract (a
required `v2` field is missing). The engine routes this through
`checkpoint_record_invalid` per §10.10's amended description and
§10.12.4 — distinguishing post-migration deserialization failure (the
record + migrations produced an unloadable shape) from the
no-chain-registered case (`checkpoint_state_migration_missing`) and the
migration-function-raised case (`checkpoint_state_migration_failed`).

**Spec sections exercised:**

- §10.10 (amended) — `checkpoint_record_invalid` covers "post-migration
  state that fails to deserialize against the current state class per
  §10.12.4."
- §10.12.4 Composition — migrations are an opportunity to avoid
  `checkpoint_record_invalid` on version mismatches; they are not a
  recovery mechanism for arbitrary record corruption.

**What passes:**

- Resume raises `checkpoint_record_invalid`.
- The error is NOT `checkpoint_state_migration_missing` (the registry
  had a relevant migration) and NOT `checkpoint_state_migration_failed`
  (the migration function returned normally).

**What fails:**

- The error category is `checkpoint_state_migration_missing` — would
  mean the engine didn't notice that a chain was found and applied.
- The error category is `checkpoint_state_migration_failed` — would mean
  the engine wrapped a non-raise as a raise.
- Resume succeeds with a malformed state — would mean the engine skipped
  v2 deserialization validation.
