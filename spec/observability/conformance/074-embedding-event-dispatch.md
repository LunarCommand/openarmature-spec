# 074 — `EmbeddingEvent` dispatch on successful `embed()`

Verifies graph-engine §6's `EmbeddingEvent` typed-event dispatch contract (per proposal 0059).
A successful `EmbeddingProvider.embed()` call MUST fire `EmbeddingEvent` on the observer
delivery queue carrying the populated identity / scoping / request-side field set plus the
embedding-specific success-side fields.

**Spec sections exercised:**

- graph-engine §6 — `EmbeddingEvent` typed event variant (proposal 0059).
- observability §5.5 — typed embedding event framing paragraph.
- retrieval-provider §3 / §4 — `embed()` success path and response shape.

**Cases:**

1. `embedding_event_dispatched_with_populated_fields` — Mocked provider returns a 2-vector
   response with usage data. Asserts the typed event is observed with `provider`, `model`,
   `response_model`, `response_id`, `input_count`, `dimensions`, `usage`, and identity /
   scoping fields all populated per the spec.

**What passes:**

- Exactly one `EmbeddingEvent` in the observer's collected storage.
- Typed-event fields match the provider response and the calling node's position in the graph.

**What fails:**

- No `EmbeddingEvent` observed — the framework swallowed the typed-event emission.
- Response-side fields (`response_id`, `response_model`, `usage`, `dimensions`) missing — the
  adapter did not populate them.
- Identity / scoping fields missing (`node_name`, `namespace`, `attempt_index`) — the dispatch
  path did not wire them through.
