# 005 — Middleware Error Propagation

Verifies the §5 error-semantics rule: when a wrapped node raises and middleware does not catch,
the exception propagates as a graph-engine §4 `node_exception` with `recoverable_state` populated
and the original exception preserved as `__cause__`.

The trace_recorder's pre-phase fires before the wrapped node runs; its post-phase does NOT fire
because `await next(state)` raises. The harness records `pre_seen` / `post_seen` flags via an
out-of-band side channel (the partial-update path is unreachable when the exception propagates).

**Spec sections exercised:**

- §5 Errors raised by a node propagate through the chain.
- graph-engine §4 `node_exception` — recoverable_state populated, __cause__ preserved.

**What passes:**

- Engine raises `node_exception`. `recoverable_state` is the pre-merge state at node entry
  (`{v: 7, trace: []}`).
- The exception's `__cause__` is the original `RuntimeError("boom from failing")`.
- `outer.pre_seen == true`, `outer.post_seen == false`.

**What fails:**

- Middleware swallows the exception silently (graph completes "successfully").
- The exception is wrapped in a different error category.
- `recoverable_state` is post-merge or absent.
- The post-phase runs even though `next` raised.
