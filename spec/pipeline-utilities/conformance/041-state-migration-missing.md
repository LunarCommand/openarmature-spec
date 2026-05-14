# 041 — State Migration Missing (Empty Registry)

Saved record at `v1`, current schema at `v2`, no migrations registered.
The engine must raise `checkpoint_state_migration_missing` rather than
`checkpoint_record_invalid` — distinguishing the actionable
("register a migration") case from the unrecoverable case.

**Spec sections exercised:**

- §10.10 `checkpoint_state_migration_missing` — non-transient; the error
  payload carries the version mismatch and a description of the
  registered migration set.
- §10.12.4 Composition — version mismatches do NOT route through
  `checkpoint_record_invalid` when no migrations are registered.

**What passes:**

- Resume raises `checkpoint_state_migration_missing`.
- The error carries `from_version=v1`, `to_version=v2`, and a description
  of the (empty) registered migration set.

**What fails:**

- The error category is `checkpoint_record_invalid` — would mean the
  version mismatch wasn't routed through the migration system.
- The resume succeeds — would mean the engine silently dropped the
  version mismatch.
- The error payload is missing `from_version` / `to_version` /
  registered-set description.
