# 061 — Three-piece composition: failure isolation + retry + transient-aware node body

Verifies §6.3's *Composition with §6.1 — the three-piece pattern*. Outer
`FailureIsolationMiddleware` wraps inner `RetryMiddleware` wraps the node body. Retry exhausts;
failure isolation catches the exhaustion-propagated exception and returns the degraded update.

**Spec sections exercised:**

- §6.3 — Three-piece composition; outer-to-inner ordering (retry MUST be inner, failure
  isolation MUST be outer).
- §6.1 — Retry middleware exhaustion (per `max_attempts`) propagating the final exception.

**Cases:**

1. `retry_exhausts_then_failure_isolation_catches` — A node configured to fail with
   `provider_unavailable` on every attempt. The middleware stack is:
   - Outer: `FailureIsolationMiddleware(degraded_update={"result": "degraded"},
     event_name="extraction_failed")`
   - Inner: `RetryMiddleware(max_attempts=2)`

   Asserts the inner retry consumes both attempts (the engine dispatches 2 started/completed
   NodeEvent pairs with `attempt_index = 0` and `1` per §6.1); the second attempt's failure
   propagates from retry; the outer failure-isolation middleware catches it and returns
   `{"result": "degraded"}`. A framework-emitted failure-isolation event is observed.

**What passes:**

- Two retry attempts (attempt_index 0 and 1) emit per §6.1.
- The outer failure-isolation middleware catches the exhaustion-propagated exception.
- Engine sees the degraded return; graph reaches END.
- Framework-emitted failure-isolation event carries the full field set; the wrapped node's
  lineage tuple is `attempt_index = 1` (the final attempt — by the time failure isolation
  catches, the inner retry has consumed both attempts).

**What fails:**

- The exception propagates past failure isolation — outer middleware not applied or applied
  inside-out (catching transients before retry sees them).
- Retry runs fewer than 2 attempts — retry middleware not exhausting per `max_attempts`.
- Failure isolation catches BEFORE retry exhaustion — outer-to-inner ordering reversed (the
  load-bearing rule from §6.3's composition section is violated).
