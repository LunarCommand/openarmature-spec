# 042 — Reducer Round-Trip Warning

Verifies the `projection_reducer_round_trip` compile-time warning (graph-engine §2). Because projection-out
merges through the parent's reducer, a field projected *in* and then *back out* into the same parent field
re-merges; for a reducer that is not *round-trip-idempotent* (one for which re-applying an already-merged
value changes the field — e.g. `append` doubles the list), that re-merge corrupts the value. The warning
flags this at compile time.

`projection_reducer_round_trip` is a **warning** — compilation **succeeds** — asserted via the
`expected_compile_warning` directive (conformance-adapter §5.8), distinct from the MUST-fail
`expected_compile_error` categories. This fixture uses the **list form** throughout:
`[projection_reducer_round_trip]` asserts *exactly* that one warning (an exhaustive, order-insensitive set)
and `[]` asserts *no* compile warning — so the no-warn cases fail an over-warning implementation. The
warning is **MUST** for the §2 canonical non-idempotent reducers (`append`, `concat_flatten`,
`bounded_append`, `merge_all`), whose idempotency is statically determinable; **SHOULD** for custom
reducers. Round-trip-idempotent canonical reducers (`last_write_wins`, `merge`, `merge_by_key`,
`dedupe_append`) do not warn.

**Round-trip condition.** A projection round-trips a field when the same parent field is copied in and a
subgraph field carrying it is merged back into that same parent field, via any of three shapes: **(a)** the
declared same-name form (`projects_in` / `projects_out`) — a name present in *both* sets; **(b)** the
explicit maps — a parent field that is both an `inputs` value and an `outputs` key mapped to the *same*
subgraph field; **(c)** the explicit maps with `outputs` *absent* (projection-out at the field-name-matching
default) — an `inputs` entry copying a parent field into a *same-named* subgraph field, so name-matching
merges it straight back out. A parent field touched via *different* subgraph fields (in vs out) is not a
round-trip; nor is a field copied *in* but never projected *out*.

**Spec sections exercised:**

- §2 Subgraph — *Reducer round-trip warning.* Round-trip idempotency classification of the canonical
  reducers; MUST-warn for a round-trip into a non-idempotent canonical reducer; the structural round-trip
  condition (same subgraph field in and out, same parent field).

**Cases:**

1. `round_trip_into_append_warns` — `log` in both `projects_in` and `projects_out`; parent reducer `append`
   → compiles, `expected_compile_warning: [projection_reducer_round_trip]`.
2. `round_trip_into_last_write_wins_no_warning` — `status` in both sets; parent reducer `last_write_wins`
   (idempotent) → `expected_compile_warning: []` (no warning); also runnable, asserts the merged value.
3. `different_subgraph_fields_no_warning` — explicit maps; `acc` is an `inputs` value and an `outputs` key
   but via *different* subgraph fields (`sg_in` in, `sg_out` out); parent reducer `append` →
   `expected_compile_warning: []` (the value merged back is not the round-tripped one); also runnable,
   asserts the merged value.
4. `inputs_only_default_out_round_trip_warns` — trigger shape (c): explicit maps with
   `inputs: {shared: shared}` and **no** `outputs`, so projection-out falls to field-name matching and
   merges subgraph `shared` back into parent `shared` (reducer `append`) → compiles,
   `expected_compile_warning: [projection_reducer_round_trip]`. Compile-only; this shape previously shipped
   unwarned.
5. `non_round_tripped_append_field_no_warning` — negative control: `projects_in: [log], projects_out: []`
   with parent `log` reducer `append`; `log` is copied in but never projected out → not a round-trip →
   `expected_compile_warning: []`. Compile-only; isolates the round-trip structure from mere
   append-presence.

**What passes:**

- Case 1 — compilation succeeds and the captured compile-time warnings are *exactly*
  `[projection_reducer_round_trip]`.
- Case 2 — compilation succeeds with *no* compile-time warning (`expected_compile_warning: []`), and
  `status == "done"` (last_write_wins is idempotent under re-application, so the round-trip does not corrupt).
- Case 3 — compilation succeeds with *no* compile-time warning (`expected_compile_warning: []`), and
  `acc == ["p0", "computed"]` (`"p0"` appears once — a genuine round-trip would double it). The trigger is
  same-*subgraph*-field round-trip, not merely same-parent-field, so a distinct `inputs`/`outputs` subgraph
  field is a correct non-warning.
- Case 4 — compilation succeeds and the captured warnings are *exactly* `[projection_reducer_round_trip]`:
  `outputs` absent means projection-out is field-name matching, which round-trips `shared` back into its
  `append` parent (trigger shape (c)).
- Case 5 — compilation succeeds with *no* compile-time warning (`expected_compile_warning: []`): `log` is an
  `append` field the subgraph touches, but it is projected in and never out, so there is no round-trip.

**What fails:**

- Case 1 or 4 — compilation fails (the diagnostic is a warning, not an error), or no
  `projection_reducer_round_trip` warning is emitted for a round-trip into a canonical non-idempotent
  reducer (a MUST), or an *extra* warning is emitted (the list form is exhaustive).
- Case 2, 3, or 5 — a `projection_reducer_round_trip` warning *is* emitted (`expected_compile_warning: []`
  is exhaustive, so any warning fails an over-warning implementation), or the case is treated as a compile
  error, or (cases 2/3) `final_state` mismatches (e.g. a doubled `acc` in case 3, which would indicate the
  impl round-tripped the value through the reducer).

**Advisory note (informative):**
All cases exercise **canonical** reducers, for which the warning is MUST (present) or MUST-not (absent) —
never the SHOULD-level custom-reducer heuristic, which this fixture does not assert in either direction. The
no-warn cases (2, 3, 5) assert warning *absence* exhaustively via `expected_compile_warning: []`, so an
implementation that over-warns on an idempotent reducer (case 2), a different-subgraph-field pairing (case
3), or an in-only append field (case 5) fails — the empty list makes absence load-bearing, not merely
implied by a runnable `final_state`.
