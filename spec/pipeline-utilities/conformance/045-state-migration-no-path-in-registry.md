# 045 — State Migration No Path in Registry

Saved record at `v1`, current schema at `v2`, migrations registered but
none form a chain from `v1` to `v2` (a `v3 -> v4` migration is registered,
unrelated to the path the engine needs). Per §10.12.2 step 4, this raises
`checkpoint_state_migration_missing` — the same category as the
empty-registry case (fixture 041), but the error's migration-set
description carries the registered (unhelpful) migrations so the user can
see what IS available.

Complements fixture 041 to verify the error category surfaces uniformly
across both empty and no-path-found registry states.

**Spec sections exercised:**

- §10.12.2 step 4 — `checkpoint_state_migration_missing` is raised when
  no path exists, regardless of whether the registry is empty or merely
  unhelpful.
- §10.10 — the error payload's "description of the registered migration
  set" reflects the registered (but unhelpful) migrations.

**What passes:**

- Resume raises `checkpoint_state_migration_missing` (same category as
  fixture 041).
- The error payload's registered-migrations description has count 1
  (one irrelevant migration registered).
- `from_version=v1`, `to_version=v2` (the path the engine needed but
  couldn't find).

**What fails:**

- The error is a different category (e.g., the engine treated unhelpful
  registrations as "no path" → `checkpoint_record_invalid`).
- The error's migration-set description is empty (would mean the engine
  didn't distinguish empty-registry from no-path-found).
