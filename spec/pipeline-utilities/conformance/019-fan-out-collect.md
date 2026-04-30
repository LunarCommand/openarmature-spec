# 019 — Fan-Out Collect

Verifies §9.5 `error_policy: "collect"` semantics: all instances run; successes contribute to
`target_field` in input order; failures' slots are OMITTED (not preserved); per-instance errors
are recorded in the parent's `errors_field`. Fan-out itself does NOT raise; downstream nodes
execute normally.

**Spec sections exercised:**

- §9.5 collect policy — successes-only `target_field`; failures recorded in `errors_field`.
- §9.5 collect failure-slot handling — failure slots are OMITTED, not preserved with a sentinel
  (the design decision from review Q2).
- §9 errors_field config — list-typed parent field with extending reducer.
- §9.3 Per-instance fan-in — slots are dense (only successes contribute); input order preserved.

**What passes:**

- Final `results == [0, 2]` — successes only, in input order.
- Final `errors` carries one entry: `{fan_out_index: "1", category: "node_exception"}`.
- `downstream_ran == true` — the `after` node executed (fan-out didn't raise).
- `execution_order == [process, after]` — confirms downstream proceeded.

**What fails:**

- `results` includes a sentinel value (`null`) at index 1 — slot preservation when the spec
  requires omission.
- `errors_field` is empty despite a failure occurring.
- `downstream_ran == false` — fan-out raised when it shouldn't have.
- `results` reflects completion order rather than input order.
