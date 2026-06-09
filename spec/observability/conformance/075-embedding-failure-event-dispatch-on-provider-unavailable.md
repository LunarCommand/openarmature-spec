# 075 — `EmbeddingFailedEvent` dispatch on `provider_unavailable`

Verifies graph-engine §6's `EmbeddingFailedEvent` typed-event dispatch contract (per proposal
0059). An `embed()` call that raises an llm-provider §7 error MUST fire `EmbeddingFailedEvent`
on the observer delivery queue AND the exception MUST still raise out of the call — the two
surfaces compose without conflict.

**Spec sections exercised:**

- graph-engine §6 — `EmbeddingFailedEvent` typed event variant (proposal 0059).
- observability §5.5 — typed embedding failure event framing.
- retrieval-provider §5 — `provider_unavailable` error category (inherited from llm-provider §7).

**Cases:**

1. `embedding_failure_event_dispatched_on_provider_unavailable` — Mocked provider returns
   HTTP 503; the implementation classifies the response as `provider_unavailable`. Asserts
   exactly one `EmbeddingFailedEvent` observed, zero `EmbeddingEvent` (mutual exclusion),
   the exception propagates out of `embed()`, and the typed event carries the mirrored
   identity / scoping / request-side fields plus `error_category = "provider_unavailable"`.

**What passes:**

- One `EmbeddingFailedEvent` in the observer's collected storage.
- Zero `EmbeddingEvent` for the failed call (mutual-exclusion rule).
- The exception propagates per the exception-flow contract.

**What fails:**

- No `EmbeddingFailedEvent` observed — the framework swallowed the typed-event emission.
- `EmbeddingEvent` also observed for the same call — mutual-exclusion violation.
- The exception is suppressed by the framework instead of re-raising — exception-flow
  contract broken.
