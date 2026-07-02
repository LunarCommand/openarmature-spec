# 0094: Subgraph Projection — Declared Same-Name Boundary

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-07-01
- **Targets:** spec/graph-engine/spec.md **§2 Concepts** (the *Subgraph* / *Explicit input/output mapping*
  block, ~L128–197, and the compile-error category list, ~L182–196): add a third projection form — a
  **declared same-name projection boundary** — alongside the field-name-matching default and the explicit
  `inputs`/`outputs` rename maps; make the declared form and the explicit maps **mutually exclusive** on a
  single subgraph-as-node (new compile-error category `conflicting_projection_forms`); and add a
  **reducer round-trip** compile-time warning, grounded in a round-trip-idempotency classification of the
  §2 canonical reducers. The round-trip warning also applies to the two other surfaces whose projection-out
  merges through a parent reducer — parallel-branches `subgraph` branches (spec/pipeline-utilities/spec.md
  **§11.2 / §11.4**) and fan-out (**§9.1 / §9.3**, `inputs` / `extra_outputs`) — which each gain a one-line
  pointer to the §2 warning. The declared same-name *form* is scoped to the general subgraph-as-node only;
  extending it to the branch / fan-out config surfaces (which keep their map-typed fields) is out of scope.
  This proposal does **not** touch pipeline-utilities §4 (which is about middleware locality, not
  projection).
- **Related:** 0002 (added the explicit `inputs`/`outputs` mapping; the declared same-name form reuses that
  mapping's per-field semantics for same-name pairs and its `mapping_references_undeclared_field` compile
  validation — it is a restricted, same-name spelling, not a superset)
- **Supersedes:**

## Summary

A small, additive reconciliation of the subgraph-projection contract (graph-engine §2), addressing two
sharp edges of the current model without changing any existing behavior:

1. A **declared same-name projection boundary** — a subgraph-as-node MAY name the fields that cross the
   boundary as two field-name *sets* (in and out) rather than the full rename maps. The named fields are
   compile-validated against both schemas, so a rename or typo on either side becomes a compile error
   instead of a silently-dropped field. It is the missing middle between the *implicit, unchecked*
   field-name-matching default and the *fully-explicit* `inputs`/`outputs` maps: declared and checked, but
   free of rename-map boilerplate for the common case where the field names already agree.

2. A **reducer round-trip warning** — the projection merge deliberately uses the parent's reducers (like
   any node's return), which means a field projected *in* and then *back out* through a reducer that grows
   on re-application (e.g. an append reducer) merges twice and doubles. Implementations SHOULD warn at
   compile time when a projection round-trips a field into such a reducer.

Both are behaviorally-normative, so a second implementation matches the first rather than being free to
choose a different presence-check rule or a different stance on round-tripped reducers — either of which
would let two identical-looking graphs produce different state on the two implementations.

## Motivation

graph-engine §2 already specifies the subgraph-projection contract well: no projection in by default;
field-name matching on the way out; explicit `inputs` (additive) / `outputs` (replacing) rename maps with
compile-time field-existence validation (`mapping_references_undeclared_field`); and — importantly — the
projected result is merged into the parent through the parent's reducers, exactly as an ordinary node's
return is. This proposal does not revisit any of that. It closes two gaps that surfaced wiring a real
read-hydration subgraph with the default projection.

**Gap 1 — the convenient default is unchecked, so name drift is silent.** The field-name-matching default
carries a field across the boundary purely because the two schemas *happen* to share a field name. That
dependency is invisible and nothing enforces it: rename or drop the field on one side and the projection
quietly stops carrying it — no compile error, no runtime error, the field simply arrives at its schema
default. A defensive downstream fallback (`value or <empty>`) then turns that into a valid-but-wrong result
far from the rename. The explicit `inputs`/`outputs` maps fix this (they are compile-validated), but they
re-introduce the per-field rename boilerplate the default exists to avoid, and authors reach for them
reactively — after being bitten — not by default. There is room between "implicit name-matching" and "full
rename map": a boundary that is *declared* (so it is checked) but expressed as bare field names (so it stays
terse) for the common case where the names already line up.

**Gap 2 — round-tripping a field through a growing reducer doubles it.** Because projection-out merges
through the parent's reducer (the correct, engine-consistent behavior — a subgraph node returns a partial
update like any node), a field that is projected *in* (its parent value copied into the subgraph) and then
projected *back out* into the same parent field re-merges through that field's reducer. For a
replace/idempotent reducer this is harmless; for a reducer that grows on re-application (append and
kin) the unchanged value is added a second time and the field doubles. This is not a defect in
projection-out semantics — "replace" would make subgraph returns inconsistent with every other node return
— but it is a trap worth flagging at compile time.

**Cross-implementation parity.** The projection boundary is already behaviorally-normative (graph-engine
§2). Without a shared contract for the declared boundary and the round-trip hazard, a second implementation
would be free to diverge — a different presence-check rule, or a different stance on round-tripped reducers,
would make two identical-looking graphs produce different state on the two implementations. Pinning both
keeps the boundary uniform across implementations.

## Proposed change

### graph-engine §2 — declared same-name projection boundary

Extend the *Subgraph* projection contract with a third, opt-in form alongside the field-name-matching
default and the explicit `inputs`/`outputs` maps. A subgraph-as-node MAY declare its boundary as two sets of
field names:

- an **in-set** — the fields projected in; at entry, each named field's current parent value is copied into
  the subgraph field **of the same name**; and
- an **out-set** — the fields projected out; at exit, each named subgraph field is merged into the parent
  field **of the same name**, via the parent's reducer.

Per-field semantics match the explicit maps restricted to same-name pairs: an in-set entry behaves as an
`inputs` entry whose subgraph and parent field names coincide; an out-set entry behaves as an `outputs`
entry whose parent and subgraph field names coincide. Subgraph fields not named in the in-set receive their
schema-declared defaults (no field-name-matching fallback for the in direction); subgraph fields not named
in the out-set are discarded.

The declared form differs from the maps in one deliberate respect — **it is a complete boundary
declaration, with no fallback to field-name matching.** Using the declared form is an explicit, checked
statement of exactly what crosses:

- The **in-set** fully determines projection-in: an empty in-set projects nothing in (identical to the
  no-projection-in default).
- The **out-set** fully determines projection-out, replacing field-name matching: an empty out-set projects
  nothing out. There is no "absent out-set falls back to name-matching" state for the declared form — a
  subgraph-as-node that wants implicit field-name matching simply does not use the declared form (it uses
  the default). This removes the maps' absent-vs-empty subtlety for the set form: an empty set means
  "nothing," symmetrically for both directions, with no hidden fallback an accidentally-empty collection
  could trigger.

**Compilation MUST fail** with the existing category `mapping_references_undeclared_field` if a declared
in-set or out-set names a field not present on the relevant schema (a parent field absent from the parent
schema, or a subgraph field absent from the subgraph schema). This reuses 0002's validation and is the whole
point: it turns the default's silent name-drift into a compile error.

**The declared form and the explicit `inputs`/`outputs` maps are mutually exclusive on a single
subgraph-as-node.** A node declares its projection with at most one of: the default (nothing declared), the
declared same-name sets, or the explicit maps. Declaring both the same-name sets and an explicit map on the
same node MUST fail compilation with a new category `conflicting_projection_forms`. (A node needing a mix of
same-name and renamed pairs uses the explicit maps for all of them — a same-name pair is simply a map entry
whose two names coincide.)

### graph-engine §2 — reducer round-trip warning

**Round-trip-idempotent reducer.** A reducer is *round-trip-idempotent* when re-applying an
already-merged value leaves the field unchanged. Of the §2 canonical reducers: `last_write_wins`, `merge`,
`merge_by_key`, `dedupe_append`, and `merge_all` are round-trip-idempotent (a replace, a keyed or
deduplicated merge, or a mapping-merge re-applied with the same value is a no-op); `append`,
`concat_flatten`, and `bounded_append` are **not** (they grow the field on re-application). A custom
(user-registered) reducer's idempotency is implementation-classified where determinable.

**Round-tripped field.** A projection *round-trips* a field when the same parent field is copied into the
subgraph and a subgraph field carrying it is merged back into that same parent field — in the declared
same-name form, a field name present in **both** the in-set and the out-set; in the explicit maps, a parent
field that is both an `inputs` source and the `outputs` target **of the same subgraph field** (e.g. `inputs`
maps subgraph `s` → parent `p` and `outputs` maps parent `p` → subgraph `s`). A parent field that is an
`inputs` source and an `outputs` target via *different* subgraph fields is not a round-trip (the value
merged back is a distinct, subgraph-computed value).

**The warning.** Implementations **SHOULD** emit a compile-time **warning** — distinct from the MUST-fail
compile-error categories — when a projection round-trips a field into a parent reducer that is not
round-trip-idempotent. The advisory identifier is `projection_reducer_round_trip`. Authors SHOULD either
route such a field through a replace/idempotent reducer or not round-trip it (e.g. keep the subgraph
read-only with respect to that field and have the parent read it directly).

This is a **SHOULD**, and it is a **structural heuristic**: an implementation cannot statically prove the
subgraph left the value unchanged, so the warning MAY fire on a round-trip that legitimately replaces the
value (a false positive that is acceptable for an advisory). It SHOULD nonetheless fire on the structural
condition above, so implementations agree on when it is raised. For a custom reducer whose idempotency an
implementation cannot determine, the implementation MAY omit the warning. The warning changes no runtime
behavior — projection-out still merges through the parent's reducer in every case.

### pipeline-utilities §11 / §9 — the round-trip warning applies; the set form does not extend

The `projection_reducer_round_trip` warning applies wherever a subgraph projection-out merges through a
parent reducer, which includes two pipeline-utilities surfaces beyond the general subgraph-as-node:

- **Parallel-branches `subgraph` branches** (§11.2 in / §11.4 out) — a field carried in via the branch
  `inputs` and back out via the branch `outputs` through the same subgraph field, into a
  non-round-trip-idempotent parent reducer, round-trips and SHOULD warn.
- **Fan-out** (§9.1 `inputs` / §9.3 `extra_outputs`) — a field carried in via `inputs` and back out via
  `extra_outputs` through the same subgraph field, into a non-round-trip-idempotent reducer, round-trips
  and SHOULD warn.

Each section gains a one-line pointer to the §2 warning; no other behavioral change. The **declared
same-name set form is NOT added to these surfaces** in this proposal — the branch spec (§11.1.1) and the
fan-out config (§9) carry map-typed `inputs` / `outputs` / `extra_outputs` fields, and adding a
set-typed field to them is a config-schema change deferred to a future proposal. (This proposal makes **no**
change to pipeline-utilities §4, which governs middleware locality across the subgraph boundary, not
projection.)

## Conformance test impact

New graph-engine fixtures (numbers assigned at Accept):

- **Declared boundary — happy path.** A subgraph-as-node with a declared in-set and out-set of same-name
  fields projects the named fields correctly (in copied at entry, out merged through the parent's reducer)
  and discards non-declared subgraph fields.
- **Declared boundary — drift caught.** Compilation fails with `mapping_references_undeclared_field` when a
  declared in-set or out-set names a field absent on the parent or the subgraph schema — the fixture that
  proves the silent-drift hazard is now a compile error.
- **Declared boundary — empty out-set projects nothing.** A present-but-empty out-set projects nothing out
  (no field-name-matching fallback), distinguishing the declared form's "complete declaration" semantics
  from the default. Paired with a default-form fixture (no declaration) that *does* field-name-match, so the
  distinction is pinned and a divergent impl that falls back on an empty set fails.
- **Conflicting projection forms.** Declaring both the same-name sets and an explicit `inputs`/`outputs` map
  on one subgraph-as-node fails compilation with `conflicting_projection_forms`.
- **Reducer round-trip.** A field round-tripped (same subgraph field in and out, same parent field) into a
  non-round-trip-idempotent canonical reducer (e.g. `append`) surfaces the `projection_reducer_round_trip`
  warning; a round-trip into a round-trip-idempotent reducer (e.g. `last_write_wins`) does not; and an
  `inputs`/`outputs` pair touching the same parent field via *different* subgraph fields does not (the
  no-false-positive case). A parallel fan-out fixture (`inputs` + `extra_outputs`) exercises the warning on
  that surface.

Because the round-trip warning is advisory (SHOULD), its fixtures assert the *identifier and structural
condition* an implementation that warns MUST use, not that every implementation warns; the exact conformance
shape for a SHOULD-level compile warning (vs the existing MUST-fail diagnostics) is settled at Accept and may
require a conformance-adapter primitive for asserting compile warnings distinctly from compile errors.

Existing subgraph-projection fixtures (default field-name matching, explicit `inputs`/`outputs`) are
unaffected — this proposal adds a form, a compile category, and a warning; it changes none of their behavior.

## Versioning

**MINOR bump** (pre-1.0), additive. A new opt-in projection form, one new compile-error category
(`conflicting_projection_forms`, reachable only by the new form), and an advisory compile-time warning; the
field-name-matching default and the explicit `inputs`/`outputs` maps are unchanged, so existing graphs and
fixtures are unaffected. Tentative spec version target deferred to Accept.

## Alternatives considered

1. **Make projection-out "replace" (bypass the parent's reducer).** Reject — it would make subgraph nodes
   the one node type whose return does not merge through the parent's reducers, an inconsistency (a
   special-cased boundary rather than a uniform model). The round-trip doubling is a reducer-choice concern,
   addressed by the warning, not a defect in the merge model.
2. **A compile-time audit that logs the resolved in/out sets on the unchecked default.** Reject — it is a
   weak mitigation (it surfaces drift only in a log diff, and only for authors who stay on the unchecked
   default), it is not behavior and is poorly conformance-testable, and the declared boundary is the real
   fix (drift becomes a compile error, not a log line).
3. **Make the field-name-matching default itself compile-checked.** Reject — breaking. The default's entire
   value is zero-declaration convenience; existing graphs rely on carrying whatever names happen to match.
   The opt-in declared boundary preserves the default and adds a safe path for authors who want the check.
4. **Status quo: "just use the explicit `inputs`/`outputs` maps."** Reject — the maps re-introduce the
   rename-map boilerplate for the common same-name case, so authors default to the unchecked path and reach
   for the maps only reactively. The declared set is the terse, checked middle.
5. **Make the reducer round-trip a MUST compile error.** Reject — reducer idempotency is not always
   statically determinable (custom reducers), and some round-trips legitimately replace the value; a hard
   error would over-constrain. SHOULD-warn fits the certainty available.
6. **Give the declared form the maps' absent-vs-empty fallback (absent out-set → field-name matching).**
   Reject — for a *set*, an empty collection is an easy accidental value, so a silent fallback on absence
   (with "project nothing" on empty) is a footgun and is asymmetric between the directions. Making the
   declared form a complete declaration (empty = nothing, no fallback, both directions) is deterministic and
   removes the trap; authors who want field-name matching use the default form.
7. **Extend the declared set form to the parallel-branches and fan-out config surfaces in this proposal.**
   Reject (for now) — those surfaces carry map-typed config fields; adding a set-typed field is a
   config-schema change with its own conformance surface. Scope this proposal to the general
   subgraph-as-node and defer the branch / fan-out set form to a follow-on if demand appears. The round-trip
   *warning* still applies to those surfaces (their projection-out merges through parent reducers).

## Open questions

- **Conformance shape for a SHOULD-level compile warning.** The existing subgraph compile diagnostics are
  MUST-fail categories; a SHOULD-emit warning is a new assertion shape. Resolve at Accept whether the fixture
  asserts "an implementation that warns names it `projection_reducer_round_trip` under this structural
  condition" (advisory) or a stronger form, and whether the conformance-adapter needs a warning-capture
  primitive distinct from its compile-error capture.

## Out of scope

- **The merge-through-reducer semantics** — unchanged; a subgraph node returns a partial update merged
  through the parent's reducers, like any node.
- **Renaming across the boundary** — remains the explicit `inputs`/`outputs` maps; the declared form is
  same-name only.
- **The field-name-matching default's behavior** — unchanged; still available, still unchecked. This adds an
  opt-in checked alternative, it does not deprecate the default.
- **The declared set form on the parallel-branches / fan-out config surfaces** — those keep their map-typed
  `inputs` / `outputs` / `extra_outputs` fields; a set-typed field for them is a possible follow-on, not
  part of this proposal. (The round-trip warning does apply to them.)
