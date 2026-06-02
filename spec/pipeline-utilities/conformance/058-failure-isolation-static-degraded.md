# 058 — Failure-isolation middleware: static degraded update

Verifies §6.3's basic catch-and-degrade contract. A node wrapped with
`FailureIsolationMiddleware(degraded_update={...}, event_name="...")` that raises an exception:
the middleware catches, returns the static `degraded_update` as the node's partial update, emits
a framework-emitted failure-isolation event with `event_name` + lineage + caught-exception
record + pre/post state, and the engine continues edge resolution from the degraded return.

**Spec sections exercised:**

- §6.3 — Failure isolation middleware; static `degraded_update`; framework-emitted observer
  event field set; engine continuation rule (engine does NOT see the exception).

**Cases:**

1. `failure_isolation_static_degraded_update` — Node `failing` raises a `provider_unavailable`
   error. The middleware wraps it with `degraded_update={"result": []}` and
   `event_name="extraction_failed"`. Asserts:
   - Engine continuation: final state has `result == []` (the degraded update merged via the
     reducer); the graph reached END.
   - Observer event: a framework-emitted failure-isolation event is observed carrying
     `event_name = "extraction_failed"`, lineage matching the wrapped node (`namespace =
     ["failing"]`), `caught_exception.category = "provider_unavailable"`, the exception
     message, `pre_state` matching the input state, `post_state` matching the degraded update.

**What passes:**

- Engine sees the degraded return; no exception bubbles up; edge resolution continues.
- Framework-emitted failure-isolation event carries the full field set.
- `caught_exception` record carries category + message correctly.

**What fails:**

- The exception bubbles up to the engine — middleware did not catch.
- The framework-emitted event is absent — middleware did not emit on catch.
- The event's `event_name` is the generic default — `event_name` is required-no-default per
  §6.3.
- The event lives on `NodeEvent` (reusing `node_name` / `error`) — §6.3 mandates a distinct
  framework-emitted event kind, not a reused NodeEvent.
