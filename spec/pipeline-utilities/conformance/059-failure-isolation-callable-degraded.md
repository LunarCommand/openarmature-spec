# 059 — Failure-isolation middleware: callable degraded update

Verifies §6.3's callable-form `degraded_update`. When `degraded_update` is a callable
`(state) -> partial_update`, the middleware resolves the degraded value at catch time using the
pre-merge state the inner chain received as input.

**Spec sections exercised:**

- §6.3 — Failure isolation middleware; callable `degraded_update`; pre-merge state resolution.

**Cases:**

1. `failure_isolation_callable_degraded_update` — A node wrapped with `FailureIsolationMiddleware`
   whose `degraded_update` is a callable returning a state-derived partial update (the caller
   computes the degraded shape from the input state's `attempt_count` field). The node raises;
   the middleware invokes the callable with the input state and returns the callable's result.
   Asserts: the callable received the pre-merge input state; the engine merge applies the
   callable's return value; the framework-emitted event's `post_state` matches the resolved
   degraded update.

**What passes:**

- The callable receives the pre-merge input state (the middleware's `state` argument).
- The callable's return value is the partial update that merges via the reducer.
- The framework-emitted event's `post_state` carries the resolved degraded update.

**What fails:**

- The callable is invoked with a different state shape (e.g., a placeholder, the post-merge
  state) — the spec contract is "same `state` argument the middleware received".
- The callable's return value does not reach the engine — middleware did not propagate the
  resolved update.
