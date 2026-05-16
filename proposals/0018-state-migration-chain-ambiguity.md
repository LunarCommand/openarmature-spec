# 0018: Pipeline Utilities — State Migration Chain Ambiguity Category and Fixture

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-15
- **Accepted:**
- **Targets:** spec/pipeline-utilities/spec.md (modifies §10.10 to add error category; modifies §10.12.1 and §10.12.2 to reference the category by name); spec/pipeline-utilities/conformance/ (adds fixture 047)
- **Related:** 0014 (state-migration hooks)
- **Supersedes:**

## Summary

Name the canonical error category for state-migration chain
ambiguity (currently mandated by §10.12.1 and §10.12.2 as "a
configuration-time error" without a specified identifier), and add
fixture 047 covering both the registration-time (duplicate
`(from_version, to_version)` pair) and resolution-time (multiple
distinct shortest paths) ambiguity cases.

## Motivation

Proposal 0014 introduced state migrations and §10.12 mandates
configuration-time errors for two distinct ambiguity cases:

- **§10.12.1** — "Two migrations with the same `from_version` and
  same `to_version` MUST raise a configuration-time error (the chain
  is ambiguous)."
- **§10.12.2** — "When multiple distinct shortest paths exist (same
  edge count, different edge sequences), this is an ambiguous chain
  and the engine MUST raise a configuration-time error — the same
  category §10.12.1 raises for duplicate `(from_version, to_version)`
  pairs."

Both rules reference "the same category" but neither names it. Spec
§10.10's runtime-category list does not include an ambiguity
category. Implementations have nothing concrete to surface; harnesses
have nothing concrete to assert.

Two consequences:

- **Cross-implementation drift.** A Python implementation might
  surface this as `ValueError`; a TypeScript implementation might
  surface it as a generic `Error` or a custom class. Each is
  spec-conformant under "configuration-time error" but they cannot
  share a conformance fixture.
- **Fixture coverage gap.** Neither the §10.12.1 duplicate-pair rule
  nor the §10.12.2 multi-shortest-path rule is exercised by an
  existing fixture in `spec/pipeline-utilities/conformance/`.
  Fixtures 039–046 cover every other §10.12 rule but skip both
  ambiguity paths.

This proposal resolves both gaps in a single small change: name the
category, then add one fixture (with two cases) that exercises both
ambiguity rules against the named category.

## Detailed design

### Pipeline-utilities §10.10: add the canonical category

Insert the following entry into §10.10's category list (alphabetic
order places it adjacent to the two existing migration-related
categories):

> New canonical configuration-time category:
> `checkpoint_state_migration_chain_ambiguous` — raised when the
> registered migration set contains an ambiguity that prevents the
> engine from picking a unique chain. Two ambiguity cases trigger
> this category:
>
> - **At registration (per §10.12.1).** Two migrations registered
>   with the same `from_version` AND the same `to_version`. The
>   engine MUST raise this category at registration time (or at
>   compile time when migrations are bound to the compiled graph,
>   per the host language's binding semantics) so the configuration
>   error surfaces before any resume attempt.
> - **At chain resolution (per §10.12.2).** A request to resolve a
>   chain from `from_version` A to `to_version` B finds two or more
>   distinct shortest paths (same edge count, different edge
>   sequences). Implementations SHOULD detect this at compile time
>   when feasible by scanning the registered migration graph;
>   load-time detection is acceptable when compile-time analysis is
>   not.
>
> Non-transient. The error MUST identify the offending
> `(from_version, to_version)` pair (for the registration case) or
> the source / target version pair and a description of the
> conflicting paths (for the resolution case) in a form appropriate
> to the host language. The four migration-related categories —
> `checkpoint_record_invalid`, `checkpoint_state_migration_missing`,
> `checkpoint_state_migration_failed`, and
> `checkpoint_state_migration_chain_ambiguous` — are mutually
> exclusive on any given resume: chain-ambiguous fires at build or
> load time before either migration runs or post-migration
> deserialization is attempted, so it cannot co-occur with
> migration-failed or record-invalid.

Update the §10.10 final paragraph (the migration-categories
mutual-exclusion paragraph) to list the new category alongside the
existing three migration-related categories.

### Pipeline-utilities §10.12.1: name the category

Replace this sentence in §10.12.1:

> Two migrations with the same `from_version` and same `to_version`
> MUST raise a configuration-time error (the chain is ambiguous).

With:

> Two migrations with the same `from_version` and same `to_version`
> MUST raise `checkpoint_state_migration_chain_ambiguous` (per
> §10.10) at registration or compile time, before any resume
> attempt.

### Pipeline-utilities §10.12.2: name the category

Replace this clause in §10.12.2 step 2:

> When multiple distinct shortest paths exist (same edge count,
> different edge sequences), this is an ambiguous chain and the
> engine MUST raise a configuration-time error — the same category
> §10.12.1 raises for duplicate `(from_version, to_version)` pairs.

With:

> When multiple distinct shortest paths exist (same edge count,
> different edge sequences), this is an ambiguous chain and the
> engine MUST raise `checkpoint_state_migration_chain_ambiguous`
> (per §10.10).

The "Implementations SHOULD detect ambiguity at compile time when
feasible" guidance immediately following remains unchanged.

### New fixture: `047-state-migration-chain-ambiguous`

Two cases under one fixture:

- **`duplicate_pair_at_registration`** — register two migrations
  with the same `(from_version, to_version)` pair (`(v1, v2,
  fn_a)` and `(v1, v2, fn_b)`). The named category MUST surface
  with the new `expected_chain_ambiguity_error` primitive (defined
  below).
- **`ambiguous_shortest_paths_at_resolution`** — register a diamond
  migration graph: `v1→v2`, `v2→v4`, `v1→v3`, `v3→v4`. State at
  v4, seeded record at v1. The named category MUST surface with
  the new `expected_chain_ambiguity_error` primitive.

### New harness primitive: `expected_chain_ambiguity_error`

This proposal also introduces a new conformance harness primitive,
`expected_chain_ambiguity_error: <category>`, that asserts the
named category surfaces *at either build time or during resume*.
This preserves §10.12.2's carve-out that compile-time detection is
SHOULD-not-MUST: an implementation that detects the ambiguity at
build/compile time satisfies the assertion via the build-step
exception; an implementation that defers detection to load time
satisfies the assertion via the resume-step exception. Both paths
are spec-conformant under §10.12.2; the harness accepts either.

Existing primitives `expected_compile_error` (graph-engine fixture
007) and `expected_error` (resume blocks, e.g. fixture 045) commit
the assertion to one timing or the other; neither is the right
shape for an error category whose timing is implementation-defined
per the spec.

The harness primitive's semantics are part of what acceptance
ships, alongside the category name and the fixture YAMLs.

The companion fixture `.md` cross-references §10.12.1 and §10.12.2
and documents the OR-acceptance shape so reviewers can see how the
fixture preserves spec flexibility.

## Conformance test impact

- New fixture `spec/pipeline-utilities/conformance/047-state-migration-chain-ambiguous.{yaml,md}`
  with two cases.
- New harness primitive `expected_chain_ambiguity_error`
  recognized by the conformance harness, accepting the named
  category at either build or resume time.
- Implementations that currently silently pick a path (or silently
  use registration order) when faced with multi-shortest-path
  ambiguity will fail the resolution case until they add detection
  at either build or load time.
- Implementations that currently silently overwrite on duplicate
  `(from, to)` registration will fail the registration case until
  they add detection.

The reference implementation in `openarmature-python` is expected
to surface ambiguity at build time as part of its 0014
implementation; this fixture exercises that path. A future
implementation that defers detection to load time will pass the
same fixture via the alternate timing leg of
`expected_chain_ambiguity_error`.

## Alternatives considered

- **Leave the category implementation-defined.** Each implementation
  picks its own error class. Rejected: prevents cross-implementation
  conformance and forces the fixture to assert against a per-language
  shape (`ValueError` vs `Error` vs custom). The spec's "the same
  category §10.12.1 raises" wording already implies a shared
  identifier; this proposal makes that identifier concrete.
- **Two separate categories** — one for registration-time ambiguity,
  one for resolution-time. Rejected: the root cause is the same
  (ambiguous chain), and §10.12.2 already says they share the
  category. Splitting would require a §10.12 rewrite and add an
  unnecessary distinction for callers.
- **Fixture asserts via `expected_compile_error` only.** Rejected:
  spec §10.12.2 explicitly accepts load-time detection
  ("load-time detection is acceptable when compile-time analysis is
  not"). A compile-time-only fixture would make a spec-conformant
  load-time-detecting implementation fail conformance — fixture and
  spec disagreeing. The new `expected_chain_ambiguity_error`
  primitive accepts either timing leg, preserving §10.12.2's
  carve-out.
- **Tighten spec to MUST compile-time detection.** Rejected:
  removes the §10.12.2 carve-out for implementations whose binding
  semantics or graph-construction model doesn't support compile-time
  scanning. The carve-out exists for a reason; conformance coverage
  shouldn't strip it.
- **Skip the fixture; trust implementations.** Rejected: the gap
  is real (no current fixture exercises either §10.12.1 ambiguity
  or §10.12.2 ambiguity); without conformance coverage, drift is
  inevitable.
- **Do nothing.** Rejected: the unnamed category leaves
  implementations and harnesses without a shared identifier; the
  fixture coverage gap is unaddressed.

## Open questions

None.
