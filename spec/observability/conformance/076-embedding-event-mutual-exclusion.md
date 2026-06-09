# 076 — `EmbeddingEvent` / `EmbeddingFailedEvent` mutual exclusion

Verifies graph-engine §6's mutual-exclusion rule for the embedding typed-event pair (per
proposal 0059). The two variants MUST NOT both fire for the same `embed()` call. Mirrors
fixture 072 for the LLM-side variant pair.

**Spec sections exercised:**

- graph-engine §6 — `EmbeddingEvent` / `EmbeddingFailedEvent` mutual exclusion (proposal 0059).

**Cases:**

1. `successful_embed_emits_exactly_one_event_zero_failures` — Successful call emits exactly
   one `EmbeddingEvent` and zero `EmbeddingFailedEvent`.
2. `failed_embed_emits_exactly_one_failure_zero_events` — Failed call (HTTP 503 →
   `provider_unavailable`) emits exactly one `EmbeddingFailedEvent` and zero `EmbeddingEvent`.

**What passes:**

- Each case observes exactly one event of the expected type and zero of the opposite type.

**What fails:**

- Both variants observed for the same call — mutual-exclusion violation.
- Zero events of either type observed — framework swallowed the dispatch.
