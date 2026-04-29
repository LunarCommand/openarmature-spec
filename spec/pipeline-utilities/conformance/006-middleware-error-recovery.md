# 006 — Middleware Error Recovery

Verifies §5 / §2: middleware MAY catch exceptions raised by `next(state)` and recover by returning
a partial update. The graph completes normally; the observer event for the node has `post_state`
populated (NOT `error`), and the engine sees a successful execution.

This is the seam circuit-breaker fallback patterns sit on (catch the failure, return a default
result, keep the graph moving).

**Spec sections exercised:**

- §2 Middleware MAY list — catch exceptions raised by `next(state)` and return a partial update
  instead of raising.
- §5 Error semantics — recovered exceptions don't reach the engine.
- graph-engine §6 — observer event reflects the *recovered* outcome (post_state, no error).

**What passes:**

- Final state is `{v: 99, trace: ["recovered"]}` (the recovery partial update merged via reducers).
- Graph completes; no exception raised to the caller.
- Observer event for `failing` has `post_state == {v: 99, trace: ["recovered"]}` and `error`
  absent.

**What fails:**

- The exception still propagates to the caller (recovery didn't actually intercept).
- Observer event has `error` populated despite recovery.
- The recovery partial update is dropped instead of merged.
