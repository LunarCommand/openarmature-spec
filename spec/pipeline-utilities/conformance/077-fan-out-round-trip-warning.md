# 077 — Fan-Out Reducer Round-Trip Warning

Verifies that the graph-engine §2 `projection_reducer_round_trip` compile-time warning applies to the
fan-out surface (pipeline-utilities §9.1 `inputs` / §9.3 `extra_outputs`). A field carried into a fan-out
instance via `inputs` and back out via `extra_outputs` through the *same subgraph field*, into a
non-round-trip-idempotent parent reducer (e.g. `append`), round-trips through the reducer and re-merges —
doubling the value.

Fan-out `inputs` is `Mapping[str, str]` (`subgraph_field → parent_field`); `extra_outputs` is
`Mapping[str, str]` (`parent_field → subgraph_field`). Here parent `log` (reducer `append`) is copied into
subgraph field `carry` via `inputs: {carry: log}`, and subgraph field `carry` is merged back into parent
`log` via `extra_outputs: {log: carry}` — the same subgraph field, the same parent field: a round-trip.

`projection_reducer_round_trip` is a **warning** — compilation **succeeds** — asserted via the
`expected_compile_warning` directive (conformance-adapter §5.8), distinct from the MUST-fail
`expected_compile_error` categories. It is MUST for the §2 canonical non-idempotent reducers. This fixture
uses the exhaustive one-element list form `[projection_reducer_round_trip]` — exactly that warning, no other.

**Spec sections exercised:**

- §9.1 / §9.3 — fan-out `inputs` / `extra_outputs`; the round-trip warning pointer to graph-engine §2.
- graph-engine §2 — *Reducer round-trip warning*, applied to the fan-out surface (a field carried in via
  `inputs` and back out via `extra_outputs` through the same subgraph field).

**Cases:**

1. `fan_out_round_trip_into_append_warns` — `inputs: {carry: log}` + `extra_outputs: {log: carry}`; parent
   reducer for `log` is `append` → compiles, `expected_compile_warning: [projection_reducer_round_trip]`.

**What passes:**

- Compilation succeeds and the captured compile-time warnings are *exactly* `[projection_reducer_round_trip]`.

**What fails:**

- Compilation fails (the diagnostic is a warning, not an error).
- No `projection_reducer_round_trip` warning is emitted for a fan-out round-trip into a canonical
  non-idempotent reducer (a MUST).
