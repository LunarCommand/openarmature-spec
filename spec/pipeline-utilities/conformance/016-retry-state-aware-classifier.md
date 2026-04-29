# 016 — Retry State-Aware Classifier

Verifies the §6.1 classifier signature `(exception, state) -> bool`: user-supplied classifiers
receive both arguments and can branch on state for context-dependent retry policies.

The fixture uses a test classifier `state_aware_max_retries_remaining` that retries only when
`state.max_retries_remaining > 0` — even for exceptions the default classifier would treat as
non-transient. Two sub-cases differ only in the initial value of `max_retries_remaining`.

**Spec sections exercised:**

- §6.1 Classifier signature `(exception, state) -> bool`.
- §6.1 The pre-merge state is the same `state` argument the middleware itself received on the
  failed attempt.
- §6.1 User-supplied classifiers MAY override the default category-based judgment.

**Cases:**

1. `state_permits_retry` — `max_retries_remaining=3`. Classifier returns true on first failure;
   node retries; success on second attempt. Final state reflects success.
2. `state_blocks_retry` — `max_retries_remaining=0`. Classifier returns false on first failure;
   exception propagates immediately. Engine raises `node_exception`. The flaky_node call counter
   is exactly 1.

**What passes:**

- `state_permits_retry`: final state is `{max_retries_remaining: 3, v: 1, trace: ["target"]}`.
- `state_blocks_retry`: engine raises `node_exception`; `flaky_call_count == 1` (classifier
  blocked retry).
- The classifier received both arguments in both cases (the harness MAY add internal assertions
  on this).

**What fails:**

- The classifier is called with only `(exception)` — implementation didn't update the signature.
- `state_blocks_retry` retries anyway — classifier ignored or always-true.
- `state_permits_retry` doesn't retry — classifier always-false.
