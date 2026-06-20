# 099 — `RerankEvent` dispatch

Verifies graph-engine §6's `RerankEvent` typed-event dispatch contract. A successful
`RerankProvider.rerank()` call MUST fire exactly one `RerankEvent` on the observer delivery queue,
carrying the identity / scoping field set plus the rerank success-side fields (`response_id`,
`response_model`, `usage`, `document_count`, `top_k`, `result_count`).

**Spec sections exercised:**

- graph-engine §6 — `RerankEvent` typed event variant and dispatch contract.
- observability §5.5 / §5.5.14 — typed rerank event framing.

**Cases:**

1. `rerank_event_dispatched_with_populated_fields` — one rerank node; mocked 2-result response. The
   `RerankEvent` carries `provider`, `model`, `response_model`, `response_id`, `document_count = 2`,
   `top_k = 2`, `result_count = 2`, `usage`, and the identity / scoping fields.

**What passes:**

- Exactly one `RerankEvent` observed with the typed fields matching the provider response.
- Identity / scoping fields (`node_name`, `namespace`, `attempt_index`, `fan_out_index`,
  `branch_name`) populated.

**What fails:**

- No `RerankEvent` observed — the framework swallowed the emission.
- A success-side field (`result_count`, `document_count`, `usage`) is missing or mismatched.
