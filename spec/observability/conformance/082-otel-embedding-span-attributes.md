# 082 — OTel embedding span attributes

Verifies observability §5.5's OTel mapping for `EmbeddingProvider.embed()` calls (per proposal
0059). The embedding span carries the Stable GenAI semconv attribute subset plus the
OA-namespace embedding attributes, parented under the calling node's span. The upstream
`gen_ai.operation.name` attribute is NOT emitted in v1 per the stable-only adoption policy
(the attribute is at Development status as of v0.54.0).

**Spec sections exercised:**

- observability §5.5 — OTel embedding-attributes sub-subsection (proposal 0059).
- observability §5.5.3 — Stable GenAI semconv attribute subset.
- `docs/compatibility.md` / `GOVERNANCE.md` — stable-only upstream adoption policy.

**Cases:**

1. `otel_embedding_span_emitted_with_expected_attributes` — One embedding-calling node;
   default observer config. Asserts span name `openarmature.embedding.complete`, the Stable
   GenAI semconv subset (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.response.model`,
   `gen_ai.response.id`, `gen_ai.usage.input_tokens`), and the OA-namespace embedding
   attributes (`openarmature.embedding.input_count`, `openarmature.embedding.dimensions`).
   Asserts `gen_ai.operation.name` is absent.

**What passes:**

- Span name matches `openarmature.embedding.complete`.
- All required attributes emit with the expected values.
- `gen_ai.operation.name` is absent from the attribute set.

**What fails:**

- Wrong span name (e.g., reuses `openarmature.llm.complete`).
- `gen_ai.operation.name` emitted — the adapter adopted the upstream-Development attribute
  ahead of upstream Stable.
- OA-namespace embedding attributes missing — the adapter did not emit them.
