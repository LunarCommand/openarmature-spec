# 030 — Cohere `/v2/rerank` `top_k` → wire `top_n`

Verifies the retrieval-provider §8.4 Cohere `top_n` mapping: a supplied `top_k` MUST appear on the wire
as `top_n` (Cohere's parameter name). The absent-`top_k` ⇒ `top_n`-omitted arm is already locked by the
028 round-trip; this fixture covers the present arm.

**Spec sections exercised:**

- retrieval-provider §5 / §6 — `top_k` bounds the result count (`len(results) <= top_k` when supplied);
  results sorted by `relevance_score` descending with valid indices.
- retrieval-provider §8.4 Cohere — `/v2/rerank` `top_n` ← `top_k` (omitted when the caller passed
  `None`); response maps onto §6 with `meta.billed_units.search_units` → `RerankUsage.search_units`,
  `input_tokens` null, top-level `id` → `response_id`, and no document echo.

**Cases:**

1. `top_k_maps_to_wire_top_n` — `rerank(top_k=2)` over 3 documents. The wire request MUST carry `top_n: 2`
   alongside `{model, query, documents}` with no `return_documents` / `truncation` keys and the
   `Authorization: Bearer <api_key>` header. The mocked Cohere response returns 2 results UNSORTED (no
   document echo); the adapter MUST sort descending with valid indices and `len(results) <= top_k`.
   `meta.billed_units.search_units` 1 → `RerankUsage.search_units` 1, `input_tokens` null; top-level `id`
   → `response_id`.

**What passes:**

- The wire request carries `top_n: 2` (from `top_k=2`); `return_documents` / `truncation` absent.
- The `Authorization: Bearer <api_key>` header is present.
- Results sorted descending, each `index` valid, `len(results) <= top_k`, every `document` null.
- `search_units` surfaced, `input_tokens` null, `response_id` from the top-level `id`.

**What fails:**

- `top_n` omitted when `top_k` was supplied, or sent under a different key (e.g. `top_k`).
- `return_documents` / `truncation` emitted; the `Authorization` header missing.
- Results returned in provider order without the sort, or more than `top_k` results surfaced.
