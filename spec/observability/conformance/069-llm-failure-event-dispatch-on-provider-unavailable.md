# 069 — `LlmFailedEvent` dispatch on `provider_unavailable`

Verifies graph-engine §6's `LlmFailedEvent` typed-event dispatch contract (per proposal 0058).
A `provider.complete()` call that raises an llm-provider §7 error MUST fire `LlmFailedEvent`
on the observer delivery queue AND the exception MUST still raise out of the call — the two
surfaces compose without conflict.

**Spec sections exercised:**

- graph-engine §6 — `LlmFailedEvent` typed event variant (proposal 0058).
- observability §5.5.7 — Typed LLM failure event framing paragraph.
- llm-provider §7 — `provider_unavailable` error category.

**Cases:**

1. `llm_failure_event_dispatched_on_provider_unavailable` — Mocked provider returns HTTP 503;
   the implementation classifies the response as `provider_unavailable` per llm-provider §7.
   Asserts exactly one `LlmFailedEvent` is observed, zero `LlmCompletionEvent` (mutual
   exclusion), the exception propagates out of `provider.complete()` (exception-flow contract
   preserved), and the typed event carries the mirrored identity / scoping / request-side
   fields plus `error_category = "provider_unavailable"`.

**What passes:**

- One `LlmFailedEvent` in the observer's collected storage.
- Zero `LlmCompletionEvent` for the failed call (mutual-exclusion rule).
- `expected_error` matches `provider_unavailable` attributed to the calling node.
- Typed-event identity / scoping fields match the calling node's position in the graph.

**What fails:**

- No `LlmFailedEvent` observed — the framework swallowed the typed-event emission.
- `LlmCompletionEvent` also observed for the same call — mutual-exclusion violation.
- The exception is suppressed by the framework instead of re-raising — exception-flow
  contract broken.
- `error_category` carries a non-§7 value or is missing.
