# 047 — State Migration Chain Ambiguous

Two cases under one fixture exercising the canonical configuration-time
error category `checkpoint_state_migration_chain_ambiguous` (per §10.10).
Both ambiguity rules in §10.12 raise the same category; this fixture
covers both.

**Spec sections exercised:**

- §10.12.1 — Two migrations registered with the same `(from_version,
  to_version)` pair MUST raise
  `checkpoint_state_migration_chain_ambiguous` at registration or
  compile time, before any resume attempt.
- §10.12.2 step 2 — When chain resolution finds multiple distinct
  shortest paths between a source and target version (same edge
  count, different edge sequences), the engine MUST raise
  `checkpoint_state_migration_chain_ambiguous`.
- §10.10 — The category is configuration-time, non-transient, and
  mutually exclusive with the other migration-related categories
  (`checkpoint_state_migration_missing`,
  `checkpoint_state_migration_failed`).

**What passes:**

- **`duplicate_pair_at_registration`** — compilation fails with
  `checkpoint_state_migration_chain_ambiguous` when two migrations
  register the same `(v1, v2)` pair with different migration
  functions.
- **`ambiguous_shortest_paths_at_resolution`** — compilation fails
  with `checkpoint_state_migration_chain_ambiguous` when the
  registered migration set forms a diamond (`v1 → v2 → v4` AND
  `v1 → v3 → v4`) and the engine would need to resolve a chain
  from `v1` to `v4`.

**What fails:**

- The engine silently picks one migration (registration-order, an
  arbitrary choice, etc.) when faced with duplicate
  `(from, to)` pairs — would mean §10.12.1's MUST-raise rule is
  not honored.
- The engine silently picks one shortest path when faced with the
  diamond migration graph — would mean §10.12.2's MUST-raise rule
  is not honored.
- The engine raises a different category (e.g.,
  `checkpoint_state_migration_missing` because the engine treats
  the ambiguity as no-path-found) — would mean the routing
  invariant in §10.10 is not honored.

**Implementation note (load-time detection accommodation):**

§10.12.2 explicitly accepts load-time detection as conformant
("Implementations SHOULD detect ambiguity at compile time when
feasible … load-time detection is acceptable when compile-time
analysis is not"). This fixture asserts the compile-time path
because compile-time detection of multi-shortest-paths over a
registered migration graph IS feasible (BFS-based ambiguity
detection is polynomial). Implementations that currently surface
the error at load time pass the spec's normative requirement but
fail this fixture's assertion shape; a follow-on harness extension
accepting either compile-time or load-time detection MAY be added
if real implementations need the accommodation.
