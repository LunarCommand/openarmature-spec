# 0036: graph-engine — Fan-Out Collection Reducers (`concat_flatten`, `merge_all`)

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-05-27
- **Accepted:** 2026-05-27
- **Targets:** spec/graph-engine/spec.md (extends §2 *Concepts* — Reducer entry — required-built-in set with two new members, `concat_flatten` and `merge_all`); spec/pipeline-utilities/spec.md (broadens §9.3 *Per-instance fan-in* `target_field` reducer contract — was list-extending-only; now accepts any §2 built-in compatible with the engine-produced list of per-instance values, explicitly enumerating `append` / `concat_flatten` / `merge_all`); spec/graph-engine/conformance/ (two new fixture pairs `026-reducer-concat-flatten.{yaml,md}` and `027-reducer-merge-all.{yaml,md}`, slotted after the existing 003 / 004 / 005 reducer fixtures plus the intervening 006-025 non-reducer fixtures)
- **Related:** 0001 (graph-engine foundation — established the required-built-in reducer set; this proposal extends it), 0005 (parallel fan-out — defines the per-instance collection pattern that motivates both reducers)
- **Supersedes:**

## Summary

Add two required built-in reducers to graph-engine §2:
`concat_flatten` (for list-shaped per-instance values collected into
a flat parent list) and `merge_all` (for dict-shaped per-instance
values folded into a single parent dict). §2 currently mandates
that implementations MUST provide at least `last_write_wins`,
`append`, and `merge`; this proposal expands that set to five.

Both new reducers exist to resolve the structural mismatch
introduced when a fan-out subgraph's per-instance value is itself
collection-shaped. The fan-out engine (pipeline-utilities §9)
collects one value per successful per-instance subgraph, wrapping
each into one element of the parent's `target_field` list. When the
per-instance value is a `list[X]` or `dict[str, X]`, the parent
receives `list[list[X]]` or `list[dict]` respectively. The existing
`append` and `merge` reducers were designed for the single-value
case and cannot consume either nested shape correctly:

- `append` preserves the nesting, producing `list[list[X]]` at a
  field declared as `list[X]` — Pydantic / equivalent validation
  fails.
- `merge` requires the update itself to be a `dict`, not a
  `list[dict]` — type mismatch at the reducer boundary, fails
  via `ReducerError`.

The two new reducers are the strict N-collection analogs:
`concat_flatten` flattens one level of list nesting; `merge_all`
folds N dicts into the prior with last-write-wins per key. Both
mirror `append` / `merge`'s strict shape contract — non-matching
inputs raise `ReducerError` per §4 rather than auto-detecting and
silently choosing a fallback behavior. Picking the right reducer
for a field is a schema-modeling decision; the strict contract
makes shape mismatches fail at the boundary instead of producing
half-correct state.

No change to §4 error categories (both reducers route failures
through the existing `ReducerError` / `reducer_error` machinery),
no change to the fan-out collection contract in pipeline-utilities
§9, no change to existing `append` / `last_write_wins` / `merge`
behavior.

## Motivation

graph-engine's fan-out facility (pipeline-utilities §9) collects
one value per successful per-instance subgraph: the per-instance
subgraph's `collect_field` value becomes one element of the
parent's `target_field` list. This contract is exact for the common
case where each instance emits a single `X` and the parent collects
`list[X]`.

When each instance's `collect_field` is itself a collection — a
`list[X]` or a `dict[str, X]` — the parent's `target_field`
receives `list[list[X]]` or `list[dict]` respectively. Neither
existing reducer (`append`, `merge`) handles this:

### The list case (`concat_flatten`)

```
prior:  [a, b]
update: [[c], [d, e], []]
append: [a, b, [c], [d, e], []]   # nesting preserved
```

A state field declared as `list[X]` (because at the schema level
the field holds flat records) then fails validation: elements are
`list[X]`, not `X`. Any fan-out boundary where the per-instance
value is list-shaped hits this, and the pattern recurs across
distinct graph capabilities within a single pipeline whenever
multiple fan-out subgraphs each produce per-instance lists for
domain-specific reasons (one-to-many extraction, per-instance
candidate generation, etc.).

### The dict case (`merge_all`)

```
prior:  {a: 1, b: 2}
update: [{c: 3}, {a: 99, d: 4}]
merge:  ReducerError — update is not a dict
```

A state field declared as `dict[str, X]` collecting per-instance
contribution dicts cannot use `merge` directly: the engine wraps
each per-instance dict as one element of a list, and `merge`'s
contract requires the update itself to be a dict. The fold across
N dicts (last-write-wins per key, consistent with `merge`'s
single-dict semantics) has no built-in.

The dict case is the structural analog of the list case: a
fan-out subgraph whose per-instance state contributes keyed
records (e.g., each instance produces a `dict[str, X]` of
name → value pairs) produces `list[dict]` at the parent's
`target_field`, which `merge` cannot consume. Both new reducers
complete §2's required-built-in set for the fan-out collection
pattern.

### Workarounds and why they fail

Three workarounds exist today for either case, each with costs:

1. **Restructure the subgraph to emit a single value.** Works when
   the per-instance one-to-many shape is incidental; doesn't work
   when the per-instance multiplicity is essential to the
   prompt's effectiveness (e.g., the prompt benefits from seeing
   all candidates an instance produces together rather than
   running once per candidate, which multiplies LLM call volume and
   degrades quality).
2. **Register a custom reducer per field.** Solves the problem but
   each adopter re-derives the same ~15 lines per shape; reducer
   names and semantics drift across services and across language
   implementations.
3. **Post-process in a node downstream of the fan-out.** Adds a
   node whose only purpose is to flatten one level or fold N dicts.
   Doesn't compose with the state-schema-as-declaration pattern
   (the nested / list-of-dicts intermediate state must still
   validate).

Adopters consistently end up at workaround 2: a small custom
reducer. Codifying both shapes in §2 as required built-ins:

- Names the operations consistently across all implementations.
- Makes the conformance contract testable (one fixture per reducer
  covers each success path plus the error contracts).
- Lets the state-schema declaration be self-documenting
  (`field: Annotated[list[X], concat_flatten]` and
  `field: Annotated[dict[str, X], merge_all]` directly signal
  "fan-out target collecting list-emitting / dict-emitting
  subgraphs").

## Detailed design

### §2 reducer set — addition

§2's *Reducer* entry currently reads:

> "Implementations MUST provide at least: `last_write_wins`,
> `append` (for list-typed fields), and `merge` (for mapping-typed
> fields). Users MAY register custom reducers per field."

Updated to:

> "Implementations MUST provide at least: `last_write_wins`,
> `append` (for list-typed fields), `merge` (for mapping-typed
> fields), `concat_flatten` (for list-typed fields whose updates
> are lists of lists — e.g., fan-out target fields collecting
> list-emitting per-instance values), and `merge_all` (for
> mapping-typed fields whose updates are lists of mappings —
> e.g., fan-out target fields collecting dict-emitting per-instance
> values). Users MAY register custom reducers per field."

Two new paragraphs follow the existing reducer-definition prose,
specifying each new reducer's semantics.

#### `concat_flatten` semantics

> "**`concat_flatten` semantics.** `concat_flatten(prior, update)`
> returns the concatenation of `prior` with the one-level
> flattening of `update`. Both `prior` and `update` MUST be lists,
> and every element of `update` MUST itself be a list. Violations
> raise `ReducerError` per §4 (the engine MUST surface the
> offending field, the reducer name, and a root-cause naming the
> non-list value). Empty `update` is a no-op (returns `prior`
> unchanged). Empty sub-lists inside `update` contribute zero
> elements (the one-to-many fan-out case where an instance
> legitimately produces zero records). Implementations MUST NOT
> auto-detect whether `update` is a list of lists vs. a flat list
> — `concat_flatten` is strictly the two-level reducer; callers
> with mixed-shape requirements MUST register a custom reducer
> rather than rely on shape-dependent behavior."

#### `merge_all` semantics

> "**`merge_all` semantics.** `merge_all(prior, update)` folds the
> sequence of mappings in `update` into `prior`, applying the same
> shallow merge semantics as `merge` (later writes win on key
> conflict; non-conflicting keys from `prior` are preserved). For
> `update = [d_1, d_2, ..., d_n]`, the result is equivalent to
> applying `merge` N times sequentially: `merge(merge(...merge(merge(prior, d_1), d_2)...), d_n)`,
> so within `update` last-write-wins applies across all N dicts
> (e.g., if `d_2` and `d_n` both set key `k`, `d_n`'s value wins).
> `prior` MUST be a mapping (dict / equivalent), `update` MUST be
> a list, and every element of `update` MUST itself be a mapping.
> Violations raise `ReducerError` per §4. Empty `update` is a
> no-op (returns `prior` unchanged). Empty mappings inside
> `update` contribute zero keys. Implementations MUST NOT
> auto-detect whether `update` is a list of mappings vs. a single
> mapping — `merge_all` is strictly the list-of-mappings reducer;
> callers needing both behaviors on the same field MUST register
> a custom reducer rather than rely on shape-dependent behavior."

The strict semantics for both reducers are intentional. They are
the *duals* of `append` / `merge` for the fan-out-collection case,
not supersets. Picking the wrong reducer for a field fails fast
at the boundary instead of producing half-correct state.

### Conformance fixtures

Two new fixture pairs under `spec/graph-engine/conformance/`,
slotting after 003-reducer-last-write-wins / 004-reducer-append /
005-reducer-merge.

**`026-reducer-concat-flatten.{yaml,md}`** covering:

- **Success path.** Two nodes write to a `concat_flatten`-reduced
  list field with list-of-list updates; final state shows the
  concatenated, flattened result.
- **Empty update path.** A node writes `update = []`; final
  state shows `prior` unchanged.
- **Empty sub-list path.** A node writes `update = [[], []]`; the
  reducer emits no elements but no error.
- **Non-list-element error path.** A node writes `update = [[a],
  "not a list"]`; the engine raises `reducer_error`; the error
  surfaces the failing field and reducer.

**`027-reducer-merge-all.{yaml,md}`** covering:

- **Success path.** Two nodes write to a `merge_all`-reduced dict
  field with list-of-mapping updates; final state shows the
  cumulative shallow merge, with later writes winning on key
  conflict both within `update` and across writes.
- **Empty update path.** A node writes `update = []`; final
  state shows `prior` unchanged.
- **Empty mapping path.** A node writes `update = [{}, {}]`; the
  reducer adds no keys but no error.
- **Non-mapping-element error path.** A node writes `update =
  [{k: 1}, "not a mapping"]`; the engine raises `reducer_error`;
  the error surfaces the failing field and reducer.

Both fixtures use a permissive field type declaration (`type: list`
for 026, `type: dict` for 027 — no element constraint) so the
reducer is the layer enforcing the list-of-collections shape rather
than the typed-state validation layer.

The non-list-`update` and non-list-`prior` error contracts
(symmetrically, non-list-`update` and non-mapping-`prior` for
`merge_all`) are spec-normative — the reducer MUST raise on these
inputs per the semantics paragraphs above — but in strict-typed
implementations the typed-state validation layer catches them
BEFORE the reducer, raising a state-validation-style error rather
than `reducer_error` specifically. The fixture-covered non-element
error case is the one the reducer is GUARANTEED to be the
gatekeeper for, independent of how strict the implementation's
typed-state layer is.

No new harness DSL extensions; the existing
`state.fields.<f>.reducer` declaration syntax already supports
per-field reducer naming.

### Why not auto-flatten / auto-merge in the fan-out engine

The fan-out engine's contract (pipeline-utilities §9) is "collect
one value per successful per-instance subgraph." Auto-handling
collection-shaped values at the engine level would couple the
engine's behavior to the per-instance value's runtime shape, which:

- Breaks the legitimate-collection-emit case where the parent does
  want `list[list[X]]` or `list[dict]` preserved (e.g.,
  per-instance `list[ToolCall]` collected into `list[list[ToolCall]]`
  so callers can attribute tool calls back to their originating
  instance).
- Hides the schema-modeling decision the user has to make anyway
  (is this field flat or nested? merged or listed?) behind engine
  behavior.
- Doesn't compose with direct node writes to the same field —
  engine auto-handling works there but plain `node.update` doesn't,
  creating asymmetric write paths.

Placing the operations at the reducer level keeps the engine's
contract narrow, makes the user's schema declaration the single
source of truth for the field shape, and works symmetrically for
fan-out collection AND direct node writes.

### Why not a flag on `FanOutConfig`

A `flatten: bool` (or `merge_collected: bool`) flag on
`FanOutConfig` introduces:

- An orthogonal axis where reducer-choice and flag-choice both
  affect the final shape, with some combinations nonsensical
  (`flatten=True` + `append` would over-flatten;
  `merge_collected=True` + `concat_flatten` is meaningless).
- A two-place declaration: the user must remember to set the flag
  AND pick the right reducer.
- A site-specific scope: the flag affects this fan-out only,
  whereas the reducer is a property of the field that any writer
  (fan-out or direct) honors.

The reducer-only approach keeps the state schema self-documenting
and the write paths symmetric.

## Spec-text changes

Edits to `spec/graph-engine/spec.md` §2 — *Reducer* entry:

1. The required-built-in sentence expands from three named
   reducers to five.
2. Two new paragraphs immediately after the *Reducer* entry's
   existing prose specifying the strict semantics, error
   contracts, empty-update and empty-element semantics, and the
   explicit rejection of auto-detect — one paragraph per new
   reducer.

One cross-spec edit to `spec/pipeline-utilities/spec.md` §9.3 —
*Per-instance fan-in*:

3. The `target_field` reducer contract broadens from
   list-extending-only (`append` or user equivalent that
   concatenates list values) to any reducer compatible with the
   engine-produced list of per-instance values. Permitted §2
   built-ins are enumerated explicitly: `append`, `concat_flatten`,
   `merge_all`. User-defined reducers MAY still be used, provided
   their `update` argument accepts the engine-produced list. The
   `extra_outputs` reducer contract is unchanged.

No changes to graph-engine §3 (Execution model), §4 (Error
categories — the existing `ReducerError` / `reducer_error`
machinery covers both new reducers' failures unchanged), §5
(Determinism), §6 (Observer hooks), pipeline-utilities §9.1-§9.2
or §9.4-§9.7 (fan-out engine contract unchanged), or any other
§-section.

## Conformance fixtures

Two new pairs:

- `spec/graph-engine/conformance/026-reducer-concat-flatten.{yaml,md}`
- `spec/graph-engine/conformance/027-reducer-merge-all.{yaml,md}`

Existing reducer fixtures 003 (last-write-wins), 004 (append), 005
(merge) remain unchanged.

## Versioning

**MINOR bump v0.27.0.** Adding two new required built-ins expands
the implementations-MUST-provide set, which is an additive
normative change to the conformance surface. Pre-1.0 SemVer permits
MINOR bumps for changes that expand the conformance contract;
implementations that pass the v0.26.x graph-engine fixtures
without `concat_flatten` and `merge_all` would no longer pass
v0.27.0 conformance, which is the intended behavior — the new
required built-ins ARE the change.

No breaking changes for caller code: existing reducer declarations
(`last_write_wins`, `append`, `merge`, custom) continue to work
unchanged. The change is purely additive at the
implementation-provides-this surface.

## Backwards compatibility

- **For callers:** no breaking change. Existing graphs that use
  `append`, `last_write_wins`, `merge`, or custom reducers continue
  to work unchanged.
- **For implementations:** v0.27.0 conformance requires shipping
  both `concat_flatten` and `merge_all`. Implementations on v0.26.x
  or earlier MAY ship either ahead of v0.27.0 acceptance with no
  observable difference (they are new names in a registry that
  didn't previously include them).

## Open questions

None at draft time. The design decisions (required-built-in,
strict semantics for both reducers, naming, fixture placement,
shipping both together rather than sequentially) are answered
above. The boundary between each new reducer and a hypothetical
auto-detecting variant is explicitly drawn (reject auto-detect for
both). The boundary between either reducer and engine-level
auto-handling is explicitly drawn (reject engine-level coupling).
