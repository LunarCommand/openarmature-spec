# 060 — Failure-isolation middleware: predicate filtering

Verifies §6.3's `predicate` field — only exceptions where `predicate(exc) is True` are caught;
others propagate.

**Spec sections exercised:**

- §6.3 — Failure isolation middleware; `predicate` field; single-argument `(exception) -> bool`
  signature; default-always-true behavior.

**Cases:**

1. `predicate_catches_matching_propagates_non_matching` — A node wrapped with
   `FailureIsolationMiddleware(predicate=<matches provider_invalid_response>, ...)`. Two
   sub-runs:
   - The node raises `provider_invalid_response` — predicate matches; middleware catches;
     engine continues from degraded return.
   - The node raises `provider_invalid_request` — predicate does NOT match; exception
     propagates as `node_exception` per graph-engine §4.

**What passes:**

- Matching exception: caught, degraded return reaches engine, framework-emitted event observed.
- Non-matching exception: propagates as `node_exception`; no framework-emitted event observed.

**What fails:**

- Non-matching exception is caught — predicate filter not enforced.
- Matching exception propagates — middleware ignored the matching predicate.
- Predicate receives a multi-argument signature (e.g., `(exception, state)`) — §6.3 mandates
  the single-argument shape.
