# 141 — OTel rerank span omits usage attributes (record-null path)

Verifies observability §5.5.13's **record-null** branch (per proposal 0093): when a rerank call reports
no usage record at all (`RerankResponse.usage = null`), the OTel rerank span MUST OMIT **both**
usage-derived attributes — `gen_ai.usage.input_tokens` and `openarmature.rerank.search_units` — while
still emitting every non-usage attribute. The mock body omits the `meta.billed_units` block entirely
(`{id, model, results}`), so `usage` is null. It is a harness stand-in for a no-usage reranker, NOT a
claim that this is any specific vendor's wire shape. TEI `/rerank` is the real-world archetype of a
no-usage reranker (its actual wire differs from this mock). This is the no-usage counterpart to 107,
whose two cases exercise the two branches of a *present* usage record (search-units-only and
input-tokens-only).

**Spec sections exercised:**

- observability §5.5.13 — rerank span name, core GenAI semconv subset, OA-namespace attributes,
  conditional emission of `gen_ai.usage.input_tokens` + `openarmature.rerank.search_units` (both omitted
  when `usage = null`), deferred `gen_ai.operation.name`, default payload gating.
- retrieval-provider §6 — `RerankResponse.usage` is `record | null`; a provider that reports no usage
  yields `usage = null`.

**Cases:**

1. `rerank_span_omits_usage_attributes_when_no_usage_record` — One rerank node; default observer config.
   The mock reports no usage record (the `meta.billed_units` block is omitted). Asserts the span emits
   `gen_ai.system`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.response.id`,
   `openarmature.rerank.query_length` / `document_count` / `top_k` / `result_count`, and that **both**
   `gen_ai.usage.input_tokens` and `openarmature.rerank.search_units` are absent (alongside the
   always-deferred `gen_ai.operation.name` and the gated payload attributes).

**What passes:**

- Span name + core GenAI subset + OA-namespace counts emitted; both usage-derived attributes absent —
  no usage record to source either from; `gen_ai.operation.name` and the gated payload attributes absent.

**What fails:**

- Either usage-derived attribute emitted (e.g. `openarmature.rerank.search_units: 0` fabricated) when
  the provider reported no usage record — the record-null branch is not honored.
- A non-usage attribute dropped, or the span misnamed.
