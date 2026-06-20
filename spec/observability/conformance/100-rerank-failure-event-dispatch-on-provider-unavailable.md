# 100 — `RerankFailedEvent` dispatch on `provider_unavailable`

Verifies graph-engine §6's `RerankFailedEvent` typed-event dispatch contract. A `rerank()` call that
raises an llm-provider §7 error MUST fire `RerankFailedEvent` on the observer delivery queue AND the
exception MUST still raise out of the call — the two surfaces compose without conflict.

**Spec sections exercised:**

- graph-engine §6 — `RerankFailedEvent` typed event variant; mutual exclusion with `RerankEvent`;
  exception-flow contract.
- observability §5.5 / §5.5.14 — typed rerank failure event framing.
- retrieval-provider §7 — `provider_unavailable` error category (inherited from llm-provider §7).

**Cases:**

1. `rerank_failure_event_dispatched_on_provider_unavailable` — mocked provider returns HTTP 503,
   classified as `provider_unavailable`. Asserts exactly one `RerankFailedEvent`, zero `RerankEvent`
   (mutual exclusion), the exception propagates out of `rerank()`, and the event carries
   `error_category = "provider_unavailable"`.

**What passes:**

- One `RerankFailedEvent` in the observer's collected storage; zero `RerankEvent` for the failed call.
- The exception propagates per the exception-flow contract.

**What fails:**

- No `RerankFailedEvent` observed — the framework swallowed the typed-event emission.
- `RerankEvent` also observed for the same call — mutual-exclusion violation.
- The exception is suppressed instead of re-raising — exception-flow contract broken.
