# 028 — Cohere `/v2/rerank` wire round-trip

Verifies the retrieval-provider §8.4 Cohere rerank mapping on the `/v2/rerank` request and response wire
surfaces (the `return_documents` no-op is fixture 029; the `top_k` → `top_n` mapping is 030; the
rate-limit path is 031). The request carries `{model, query, documents}` (string array) with the
`Authorization: Bearer <api_key>` header and **no** `return_documents` / `truncation` / `top_n` keys; the
Cohere response maps onto §6's `RerankResponse` with the sort + valid-index invariants honored,
`meta.billed_units.search_units` → `RerankUsage.search_units`, and the top-level `id` → `response_id`.

**Spec sections exercised:**

- retrieval-provider §5 / §6 — `rerank()` MUST return results sorted by `relevance_score` descending,
  MUST preserve each result's `index` as the input-list position, and surfaces the response shape
  (`results`, `usage`, `response_id`).
- retrieval-provider §8.4 Cohere — *Construction*: the provider binds an API key sent as
  `Authorization: Bearer <key>`. `/v2/rerank` request shape `{model, query, documents: [str], top_n?}`;
  `documents` maps directly onto the wire `documents` as a **string array** (no per-document wrapping, no
  `rank_fields`); the response `{id, results: [{index, relevance_score}], meta: {billed_units:
  {search_units}}}` maps onto `results`; `meta.billed_units.search_units` → `RerankUsage.search_units`
  with `input_tokens` null (Cohere meters by search units, not tokens — the inverse of Jina §8.2);
  top-level `id` → `response_id`; Cohere echoes no document text, so every `ScoredDocument.document` is
  null; results are returned ranked but the mapping sorts regardless.
- retrieval-provider §6 — `ScoredDocument.document` MUST NOT be fabricated from the input `documents` list
  when the provider omits the echo.

**Cases:**

1. `rerank_wire_round_trip_sorted_results` — 3 documents, default config, no `top_k`. Exactly ONE POST to
   `{base_url}/v2/rerank` carrying `{model, query, documents: [...3...]}` with `top_n`, `return_documents`,
   and `truncation` ABSENT and the `Authorization: Bearer <api_key>` header present. The mocked Cohere
   response is UNSORTED; the adapter MUST sort by `relevance_score` descending with valid indices. Every
   `ScoredDocument.document` is null (Cohere echoes none); `meta.billed_units.search_units` 1 →
   `RerankUsage.search_units` 1, `input_tokens` null; top-level `id` → `response_id`.

**What passes:**

- Exactly one `/v2/rerank` request; `model` + `documents` (string array, in order) on the body; `top_n`,
  `return_documents`, and `truncation` all absent (the Cohere wire has none of them).
- The `Authorization: Bearer <api_key>` header is present on the outbound request.
- Results sorted descending; each `index` valid into the input documents; every `document` null.
- `meta.billed_units.search_units` surfaces on `search_units`; `input_tokens` null; `id` → `response_id`.

**What fails:**

- More than one request issued; `documents` reordered / wrapped per document / sent as objects; `model`
  omitted.
- `return_documents`, `truncation`, or `top_n` emitted (the Cohere wire accepts none of them here).
- The `Authorization: Bearer` header missing or carrying the wrong scheme.
- Results returned in provider order without the sort, or an `index` rewritten to the sorted position.
- A `document` fabricated from the input `documents` list (Cohere echoes none).
- `search_units` dropped, `input_tokens` fabricated, or `response_id` not sourced from the top-level `id`.
