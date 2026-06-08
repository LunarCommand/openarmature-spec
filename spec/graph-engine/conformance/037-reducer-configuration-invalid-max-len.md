# 037 — `reducer_configuration_invalid` on `bounded_append(max_len=0)`

Verifies graph-engine §2's `reducer_configuration_invalid` compile-time error category (per
proposal 0023). A reducer factory supplied invalid construction parameters MUST raise the
error at field registration / graph compilation time, before any node body runs.

**Spec sections exercised:**

- graph-engine §2 — `reducer_configuration_invalid` compile-time error category (proposal
  0023, listed alongside `conflicting_reducers` et al.).
- graph-engine §2 — `bounded_append(max_len)` MUST validate `max_len ≥ 1` at registration.

**Cases:**

1. `bounded_append_max_len_zero_raises_at_compilation` — Field declared with
   `bounded_append(max_len=0)`. The factory raises `reducer_configuration_invalid` at
   compilation; no node body runs.

**Per-suite directive:**

- `expected_compile_error: {category: <name>}` — the adapter MUST verify that graph
  compilation fails with the named compile-time error category, BEFORE any node body
  executes (paralleling the `expected_error` directive for runtime errors).

**What passes:**

- Graph compilation fails with category `reducer_configuration_invalid`.
- No node body is invoked.

**What fails:**

- The factory accepts `max_len=0` (the parameter is invalid per spec; spec mandates ≥ 1).
- The error surfaces at runtime (first node body invocation) rather than at compilation —
  the spec mandates compile-time validation for parameters checkable without invoking
  callables.
- The error category is `conflicting_reducers` or any other category — the spec carves
  `reducer_configuration_invalid` as a distinct category specifically for invalid factory
  parameters.
