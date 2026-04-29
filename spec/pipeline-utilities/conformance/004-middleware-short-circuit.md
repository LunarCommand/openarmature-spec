# 004 — Middleware Short-Circuit

Verifies the §2 short-circuit semantics: a middleware that does NOT call `next` causes the rest of
the chain (subsequent middleware AND the wrapped node) and its own post-phase to skip. The outer
middleware (which DID call `next`) still runs both phases normally.

This is the load-bearing test for cache-style and feature-flag-style middleware patterns described
in the proposal motivation.

**Spec sections exercised:**

- §2 Middleware MAY list — short-circuit by NOT calling `next`.
- §2 Pre-node and post-node phases — own post-phase is skipped when next isn't called.

**What passes:**

- Final `trace` is `["outer.pre", "short_circuit", "outer.post"]`.
- Inner trace_recorder's pre and post markers do NOT appear.
- Node `a`'s `"a"` marker does NOT appear.
- `execution_order` is empty — the engine never received a node-completion event for `a` because
  `a` never ran. (Whether the engine fires an observer event for a short-circuited node is a
  separate concern; the current spec does not. The harness asserts on the engine-level execution
  order.)

**What fails:**

- Inner middleware runs anyway (short-circuit doesn't actually skip the chain).
- Node `a` runs anyway.
- Short-circuit's own post-phase runs (it shouldn't — it didn't call `next`, so there's nothing
  to return from).
- `outer.post` doesn't fire (outer DID call next; its post-phase MUST run).
