# 047 — State Migration Chain Ambiguous

Two cases under one fixture exercising the canonical configuration-time
error category `checkpoint_state_migration_chain_ambiguous` (per §10.10).
Both ambiguity rules in §10.12 raise the same category; this fixture
covers both.

**Spec sections exercised:**

- §10.10 — `checkpoint_state_migration_chain_ambiguous` (configuration-time,
  non-transient). Mutually exclusive with the other three migration-related
  categories on any given resume.
- §10.12.1 — Two migrations registered with the same `(from_version,
  to_version)` pair MUST raise
  `checkpoint_state_migration_chain_ambiguous` at registration or
  compile time, before any resume attempt.
- §10.12.2 step 2 — When chain resolution finds multiple distinct
  shortest paths between a source and target version (same edge
  count, different edge sequences), the engine MUST raise
  `checkpoint_state_migration_chain_ambiguous`. Implementations
  SHOULD detect this at compile time when feasible; load-time
  detection is acceptable.

**New harness primitive:** `expected_chain_ambiguity_error: <category>`
accepts the named category surfacing at either build time or during
resume. Preserves §10.12.2's compile-time-SHOULD / load-time-acceptable
carve-out so implementations that detect ambiguity at either point pass
the same fixture without forcing the spec to over-tighten to MUST
compile-time.

**What passes:**

- **`duplicate_pair_at_registration`** — the
  `expected_chain_ambiguity_error` assertion fires when two
  migrations register the same `(v1, v2)` pair with different
  migration functions. Implementations that detect at registration
  time satisfy the assertion via the build-step exception.
- **`ambiguous_shortest_paths_at_resolution`** — the
  `expected_chain_ambiguity_error` assertion fires when the
  registered migration set forms a diamond (`v1 → v2 → v4` AND
  `v1 → v3 → v4`) and the engine must resolve a chain from `v1` to
  `v4`. Implementations that detect at compile time satisfy via the
  build-step exception; implementations that defer to load time
  satisfy via the resume-step exception.

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
- The engine raises the right category but at neither build nor
  resume time (e.g., wraps it inside an unrelated exception path)
  — would mean the `expected_chain_ambiguity_error` primitive's
  either-timing acceptance is not satisfied.
