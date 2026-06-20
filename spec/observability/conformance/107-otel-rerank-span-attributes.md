# 107 — OTel rerank span attributes

Verifies observability §5.5.13's OTel rerank span: the span name `openarmature.rerank.complete`, the
core GenAI semconv subset, the OA-namespace `openarmature.rerank.*` attributes, and — critically —
the two **conditional-emission** branches (`gen_ai.usage.input_tokens` and
`openarmature.rerank.search_units` are each emitted only when the provider reports the source value).
Both cases assert `gen_ai.operation.name` is NOT emitted (no upstream rerank coverage) and run under
the default payload-off posture (the `openarmature.rerank.query` / `.documents` / `.results` payload
attributes are absent).

**Spec sections exercised:**

- observability §5.5.13 — rerank span name, core GenAI semconv subset, OA-namespace attributes,
  conditional emission of `gen_ai.usage.input_tokens` + `openarmature.rerank.search_units`, deferred
  `gen_ai.operation.name`, default payload gating.

**Cases:**

1. `rerank_span_with_search_units_no_input_tokens` — provider reports `search_units` only.
   `openarmature.rerank.search_units` present; `gen_ai.usage.input_tokens` absent.
2. `rerank_span_with_input_tokens_no_search_units` — provider reports `input_tokens` only.
   `gen_ai.usage.input_tokens` present; `openarmature.rerank.search_units` absent.

**What passes:**

- Span name + core GenAI subset + OA-namespace counts emitted; each conditional attribute present
  only when its source is reported; `gen_ai.operation.name` and the gated payload attributes absent.

**What fails:**

- A conditional attribute emitted (e.g., `gen_ai.usage.input_tokens: null`) when the provider didn't
  report it — the conditional branch is not honored.
- `gen_ai.operation.name` emitted, or a payload attribute leaked under default config.
