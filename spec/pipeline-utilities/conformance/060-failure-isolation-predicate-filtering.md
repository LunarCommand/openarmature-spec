# 060 — Failure-isolation middleware: predicate filtering

Verifies §6.3's `predicate` field: only exceptions for which the predicate returns `true` are
caught; others propagate.

**Spec sections exercised:**

- §6.3: failure-isolation middleware's `predicate` field. An exception the predicate matches is
  caught, and one it does not match propagates. The default predicate, which catches every
  exception, is fixture 063's subject.

**Cases:**

In both, the node is wrapped with failure-isolation middleware whose `predicate` matches
`provider_invalid_response`.

1. `predicate_matches_catches_and_returns_degraded`: the node raises `provider_invalid_response`.
   The predicate matches, the middleware catches, and the engine continues from the degraded
   return.
2. `predicate_does_not_match_propagates_raised_error`: the node raises `provider_invalid_request`.
   The predicate does not match, so the exception propagates per graph-engine §4, and the raised
   error's category is the node's own `provider_invalid_request`.

**What passes:**

- Matching exception: caught, degraded return reaches engine, framework-emitted event observed.
- Non-matching exception: propagates, and the raised error's category is
  `provider_invalid_request`; no framework-emitted event observed.

**What fails:**

- Non-matching exception is caught — predicate filter not enforced.
- Matching exception propagates — middleware ignored the matching predicate.
