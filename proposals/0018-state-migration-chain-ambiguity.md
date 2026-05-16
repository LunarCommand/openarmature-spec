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
> to the host language. The migration system's three other
> categories — `checkpoint_state_migration_missing`,
> `checkpoint_state_migration_failed`, and
> `checkpoint_state_migration_chain_ambiguous` — are mutually
> exclusive on any given resume.

Update the §10.10 final paragraph (the migration-categories
mutual-exclusion paragraph) to list the new category alongside the
existing two.

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
  fn_a)` and `(v1, v2, fn_b)`). Compilation MUST fail with
  `expected_compile_error: checkpoint_state_migration_chain_ambiguous`.
- **`ambiguous_shortest_paths_at_resolution`** — register a diamond
  migration graph: `v1→v2`, `v2→v4`, `v1→v3`, `v3→v4`. State at
  v4, seeded record at v1. Compilation MUST fail with
  `expected_compile_error: checkpoint_state_migration_chain_ambiguous`
  (per the spec's SHOULD-detect-at-compile-time guidance; an
  implementation that defers detection to load time is conformant
  but currently outside this fixture's scope — see Alternatives).

The fixture uses the same harness primitives as fixture 045 plus
the `expected_compile_error` primitive established by graph-engine
fixture 007. No new harness primitives are required.

The companion `.md` describes both cases against §10.12.1 and
§10.12.2 and notes the load-time-detection accommodation as a
follow-on if real impls need it.

## Conformance test impact

- New fixture `spec/pipeline-utilities/conformance/047-state-migration-chain-ambiguous.{yaml,md}`
  with two cases.
- Implementations that currently silently pick a path (or silently
  use registration order) when faced with multi-shortest-path
  ambiguity will fail the resolution case until they add detection.
- Implementations that currently silently overwrite on duplicate
  `(from, to)` registration will fail the registration case until
  they add detection.

The python reference implementation's PR-4 (proposal 0014) plan
includes the registration-time duplicate-pair check; the
multi-shortest-path check was flagged as a gap in the spec-side
plan-cleared response and will be added before PR-4 merges. So this
fixture is expected to pass python on day one of acceptance.

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
- **Fixture asserts via load-time error path** rather than
  compile-time. Rejected: the spec SHOULDs compile-time detection,
  so the fixture should reward that path. A follow-on can add a
  harness primitive accepting either compile-time or load-time
  detection if implementations surface a need.
- **Skip the fixture; trust implementations.** Rejected: the gap
  is real (no current fixture exercises either §10.12.1 ambiguity
  or §10.12.2 ambiguity); without conformance coverage, drift is
  inevitable.
- **Do nothing.** Rejected: the unnamed category leaves
  implementations and harnesses without a shared identifier; the
  fixture coverage gap is unaddressed.

## Open questions

None.
