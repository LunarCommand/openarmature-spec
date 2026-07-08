# 014 — TEI `/rerank` single-batch path

Verifies the retrieval-provider §8.1 TEI rerank mapping when the candidate pool fits within one
batch (`len(documents) ≤ chunk_size`). A 3-document pool against the default `chunk_size` 32 MUST
produce exactly ONE `/rerank` request, and the TEI response MUST map onto §6's `RerankResponse` with
the sort + valid-index invariants honored.

**Spec sections exercised:**

- retrieval-provider §5 / §6 — `rerank()` MUST return results sorted by `relevance_score`
  descending, MUST preserve each result's `index`, and surfaces `ScoredDocument.document` from the
  provider echo. `RerankResponse.raw` is the verbatim deserialized provider response — for TEI
  `/rerank` a **bare result array** (§6 `raw`); a single-request call, so `raw` is that one response
  in provider order with chunk-relative indices, not the sorted/re-based `results`.
- retrieval-provider §8.1 TEI — `/rerank` request shape
  `{query, texts, truncate: false, return_text}`; `texts` maps directly onto `documents` (no
  per-document wrapping); `return_documents` → `return_text`; response `[{index, score, text?}]`
  maps onto `results`; TEI does not guarantee sort order, so the mapping sorts.

**Cases:**

1. `single_batch_one_request_sorted_results` — 3 documents, default config. Exactly ONE `/rerank`
   request carrying `{query, texts: [...3...], truncate: false, return_text: false}`. The mocked TEI
   response is UNSORTED; the adapter MUST sort by `relevance_score` descending with valid indices.
   TEI reports no id / no usage ⇒ `response_id` null, `usage` null (the record itself, not an
   all-null record — the mapping MUST NOT fabricate a `RerankUsage`).
2. `single_batch_return_documents_maps_to_return_text` — `config={return_documents: True}` ⇒ the
   wire request carries `return_text: true`; the TEI-echoed `text` per result MUST surface verbatim
   on `ScoredDocument.document`.

**What passes:**

- Exactly one `/rerank` request; `texts` equals `documents` in order; `truncate: false` always;
  `return_text` tracks `return_documents`.
- Results sorted descending; each `index` valid into the input documents; `response_id` / `usage`
  null where TEI omits them.
- `raw` equals the verbatim bare result array as the mock returns it — provider order and
  chunk-relative indices, distinct from the sorted/re-based `results`.
- The echoed `text` surfaces verbatim on `document` when `return_documents` is set.

**What fails:**

- More than one request issued for an in-cap pool, or `texts` reordered / wrapped per document.
- `truncate` omitted or sent `true`; `return_text` not tracking `return_documents`.
- Results returned in provider order without the sort, or an `index` rewritten to the sorted
  position.
- `usage` fabricated when TEI reports no billing block, or `document` auto-filled from the input list
  rather than the provider echo.
