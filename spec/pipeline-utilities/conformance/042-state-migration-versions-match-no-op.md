# 042 — State Migration Versions-Match No-Op

Saved record at `v2`, current schema at `v2`. Per §10.12.3, the engine
MUST NOT consult the migration registry when versions match. The record
loads via the §10.4 fast path.

A migration is registered to make the test meaningful — if the engine
mistakenly invoked it (e.g., it doesn't short-circuit on version
equality), the test would fail because the mock raises.

**Spec sections exercised:**

- §10.12.3 No-op when versions match — the engine MUST NOT consult the
  migration registry when the record's `schema_version` equals the
  current schema's `schema_version`.
- §10.4 Resume fast path — used unchanged when no migration is needed.

**What passes:**

- The migration is NOT invoked.
- Resume completes normally with the seeded state intact.

**What fails:**

- The migration is invoked (would mean the engine consulted the registry
  needlessly, breaking the §10.12.3 fast-path contract).
- Final state corrupted or migration's `should_not_run` mock raised.
