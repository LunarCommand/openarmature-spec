# 046 — State Migration Function Raises

A registered `v1 -> v2` migration function raises a `KeyError` during
chain application. Per §10.12.2, the engine wraps the raised exception
as `checkpoint_state_migration_failed` (per §10.10) and propagates it,
preserving the underlying exception as cause.

The fixture verifies the §10.12.2 contract that a raising migration
aborts the chain and propagates as the dedicated category — NOT as
`checkpoint_record_invalid` (which covers structural failures, not
user-code failures) and NOT as `checkpoint_state_migration_missing`
(which covers the no-chain case).

**Spec sections exercised:**

- §10.12.2 — migration-function-raise handling: wrap as
  `checkpoint_state_migration_failed`, preserve cause, abandon the chain.
- §10.10 — `checkpoint_state_migration_failed` carries `from_version`,
  `to_version`, and the underlying exception as cause.
- §10.10 — the three migration-related categories are mutually exclusive
  per the established ordering.

**What passes:**

- Resume raises `checkpoint_state_migration_failed`.
- The error exposes the underlying `KeyError` as cause.
- The error carries `from_version=v1` and `to_version=v2`.

**What fails:**

- The error category is `checkpoint_record_invalid` — would mean the
  engine treated the migration-function raise as a structural failure.
- The error category is `checkpoint_state_migration_missing` — would
  mean the engine treated the failure as no-chain-found.
- The underlying `KeyError` is dropped (would mean the cause wasn't
  preserved).
