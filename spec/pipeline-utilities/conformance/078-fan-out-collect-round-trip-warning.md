# 078 — Fan-Out Collect-Channel Round-Trip Warning

Verifies that the graph-engine §2 `projection_reducer_round_trip` compile-time warning applies to the fan-out
**primary collect channel** (`collect_field` / `target_field`), not only the `inputs` / `extra_outputs`
projection-map channel that fixture 077 exercises. A parent field seeded into each instance via `inputs` and
collected straight back out into that *same parent field* round-trips through the parent's reducer exactly as
an `extra_outputs` field does — doubling under a non-round-trip-idempotent reducer, once per instance. The
companion case pins the negative: a collect that is *not* a round-trip does not warn.

Fan-out `inputs` is `Mapping[str, str]` (`subgraph_field → parent_field`). `projection_reducer_round_trip` is
a **warning** — compilation **succeeds** — asserted via the `expected_compile_warning` directive
(conformance-adapter §5.8), distinct from the MUST-fail `expected_compile_error` categories. It is MUST for
the §2 canonical non-idempotent reducers.

**Spec sections exercised:**

- §9.1 / §9.3 — fan-out `inputs` and the primary `collect_field` / `target_field` channel; the round-trip
  warning pointer to graph-engine §2 (proposal 0111).
- graph-engine §2 — *Reducer round-trip warning*, applied to the fan-out collect channel (a `collect_field`
  seeded from `target_field` via `inputs` and collected back out into that same `target_field`), and its
  absence for a collect that is not a round-trip.

**Cases:**

1. `fan_out_collect_round_trip_into_concat_flatten_warns` — parent `results` (reducer `concat_flatten`) is
   seeded into subgraph field `acc` via `inputs: {acc: results}`, and `collect_field: acc` collects that same
   field back into `target_field: results` → round-trips → compiles with
   `expected_compile_warning: [projection_reducer_round_trip]`.
2. `fan_out_clean_collect_into_append_no_warn` — `collect_field: out` is instance-computed (not seeded from
   `results` via `inputs`) and collected into `target_field: results` (reducer `append`), with no
   `extra_outputs` → not a round-trip → compiles with `expected_compile_warning: []`. Isolated so the empty
   set catches an over-warning implementation; pins that the trigger is the round-trip condition, not "collect
   into a growing reducer."

Each case is a separate graph, so the empty assertion in case 2 stays isolated even though case 1 round-trips
— `expected_compile_warning` is an order-insensitive **set** of categories, so a round-trip on the same node
would collapse into the single entry and mask a spurious warning.

**What passes:**

- Case 1: compilation succeeds and the captured warnings are *exactly* `[projection_reducer_round_trip]`.
- Case 2: compilation succeeds and the captured warning set is *empty*.

**What fails:**

- No `projection_reducer_round_trip` warning for the collect-channel round-trip into a canonical
  non-idempotent reducer (a MUST), or a spurious warning for the clean collect (an over-warning impl).
- Compilation fails (the diagnostic is a warning, not an error; both graphs are valid).
