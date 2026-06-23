# 018 — Jina `/v1/rerank` wire round-trip

Verifies the retrieval-provider §8.2 Jina rerank mapping on the `/v1/rerank` request and response wire
surfaces (the `return_documents` default-override is fixture 019; the error paths are 021 / 022). The
request carries `{model, query, documents, return_documents, truncation: false}` with the
`Authorization: Bearer <api_key>` header; the Jina response maps onto §6's `RerankResponse` with the
sort + valid-index invariants honored and `usage.total_tokens` → `RerankUsage.input_tokens`.

**Spec sections exercised:**

- retrieval-provider §5 / §6 — `rerank()` MUST return results sorted by `relevance_score` descending,
  MUST preserve each result's `index` as the input-list position, and surfaces the response shape
  (`results`, `usage`, `response_id`).
- retrieval-provider §8.2 Jina — *Construction*: the provider binds an API key sent as
  `Authorization: Bearer <key>`. `/v1/rerank` request shape
  `{model, query, documents, top_n?, return_documents, truncation: false}`; `documents` maps directly
  onto `documents` (no per-document wrapping); `top_n` ← `top_k` (absent here); response
  `{model, usage: {total_tokens}, results: [{index, relevance_score, document?}]}` maps onto `results`;
  `usage.total_tokens` → `RerankUsage.input_tokens` (Jina meters rerank by tokens, not search units);
  results are returned ranked but the mapping sorts regardless.

**Cases:**

1. `rerank_wire_round_trip_sorted_results` — 3 documents, default config, no `top_k`. Exactly ONE POST
   to `{base_url}/v1/rerank` carrying `{model, query, documents: [...3...], return_documents: false,
   truncation: false}` with `top_n` ABSENT and the `Authorization: Bearer <api_key>` header present.
   The mocked Jina response is UNSORTED; the adapter MUST sort by `relevance_score` descending with
   valid indices. `usage.total_tokens` 57 → `RerankUsage.input_tokens` 57, `search_units` null;
   `response_id` null (Jina returns no id here).

**What passes:**

- Exactly one `/v1/rerank` request; `model` + `documents` (in order) on the body; `return_documents`
  and `truncation` both `false`; `top_n` absent when `top_k` is not supplied.
- The `Authorization: Bearer <api_key>` header is present on the outbound request.
- Results sorted descending; each `index` valid into the input documents.
- `usage.total_tokens` surfaces on `input_tokens`; `search_units` null; `response_id` null where Jina
  omits them.

**What fails:**

- More than one request issued; `documents` reordered / wrapped per document; `model` omitted.
- `truncation` omitted or sent `true`; `top_n` emitted when no `top_k` was supplied.
- The `Authorization: Bearer` header missing or carrying the wrong scheme.
- Results returned in provider order without the sort, or an `index` rewritten to the sorted position.
- `total_tokens` dropped, mapped to the wrong field, or `search_units` / `response_id` fabricated when
  Jina omits them.
