# 078 — Fan-Out Collect-Channel Round-Trip Warning

Verifies that the graph-engine §2 `projection_reducer_round_trip` compile-time warning applies to the fan-out
**primary collect channel** (`collect_field` / `target_field`), not only the `inputs` / `extra_outputs`
projection-map channel that fixture 077 exercises. A parent field seeded into each instance and collected
straight back out into that *same parent field* round-trips through the parent's reducer — doubling under a
non-round-trip-idempotent reducer, once per instance.

The collect field can be seeded from `target_field` by **either** fan-out projection-in mechanism (§9.1):

- **`inputs` whole-value copy** — an `inputs` entry keys `collect_field` to `target_field` (proposal 0111); or
- **`items_field` / `item_field` per-item spread** — `item_field == collect_field` and
  `items_field == target_field`, the **default** fan-out mode (proposal 0112): each element of the
  `target_field` list is spread into the collected field.

`projection_reducer_round_trip` is a **warning** — compilation **succeeds** — asserted via the
`expected_compile_warning` directive (conformance-adapter §5.8), distinct from the MUST-fail
`expected_compile_error` categories. It is MUST for the §2 canonical non-idempotent reducers.

**Spec sections exercised:**

- §9.1 / §9.3 — fan-out `inputs`, `items_field` / `item_field`, and the primary `collect_field` /
  `target_field` channel; the round-trip warning pointer to graph-engine §2 (proposals 0111 + 0112).
- graph-engine §2 — *Reducer round-trip warning*, applied to the fan-out collect channel under both seeding
  spellings, and its absence for a collect that is not a round-trip.

**Cases:**

1. `fan_out_collect_round_trip_into_concat_flatten_warns` — **inputs-seeded round-trip.** Parent `results`
   (reducer `concat_flatten`) is seeded into subgraph field `acc` via `inputs: {acc: results}`, and
   `collect_field: acc` collects that same field back into `target_field: results` → round-trips → compiles
   with `[projection_reducer_round_trip]`.
2. `fan_out_clean_collect_into_append_no_warn` — **clean collect, no round-trip.** `collect_field: out` is
   instance-computed (not seeded from `results` via `inputs`), collected into `target_field: results`
   (`append`), with no `extra_outputs` → `expected_compile_warning: []`.
3. `fan_out_item_seeded_collect_round_trip_into_append_warns` — **item-seeded round-trip (default mode).**
   Parent `results` (`append`) is spread element-wise into subgraph `item` via `items_field` / `item_field`,
   and `collect_field: item` collects that same field back into `target_field: results`
   (`item_field == collect_field`, `items_field == target_field`) → round-trips → `[projection_reducer_round_trip]`.
4. `fan_out_item_seeded_collect_different_field_no_warn` — **item-seeded, different collect field.** `results`
   is fanned over (`items_field == target_field`) but the collected field `other` is not the seeded `item`
   (`item_field != collect_field`), so the seeded elements do not round-trip → `expected_compile_warning: []`.
   Pins that fanning over `target_field` alone does not trigger; only collecting the *seeded* field back does.

Each case is a separate graph, so the empty assertions (2, 4) stay isolated even though 1 and 3 round-trip —
`expected_compile_warning` is an order-insensitive **set** of categories, so a round-trip on the same node
would collapse into the single entry and mask a spurious warning.

**What passes:**

- Cases 1, 3: compilation succeeds and the captured warnings are *exactly* `[projection_reducer_round_trip]`.
- Cases 2, 4: compilation succeeds and the captured warning set is *empty*.

**What fails:**

- No `projection_reducer_round_trip` warning for a collect-channel round-trip (either seeding spelling) into a
  canonical non-idempotent reducer (a MUST), or a spurious warning for a non-round-trip collect (an
  over-warning impl).
- Compilation fails (the diagnostic is a warning, not an error; all four graphs are valid).
