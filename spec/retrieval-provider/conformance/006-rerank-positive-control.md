# 006 — `RerankProvider.rerank()` positive control

Verifies the rerank response-shape contract from retrieval-provider §5 / §6. A bound
`RerankProvider` whose mocked provider returns scored documents **unsorted** by score MUST return
them sorted by `relevance_score` descending, with each result's `index` preserved as the position in
the input `documents` list, usage populated, and `response_id` surfaced.

**Spec sections exercised:**

- retrieval-provider §5 — `rerank()` operation; MUST return results sorted by `relevance_score`
  descending and MUST preserve each result's `index` as the input-documents position.
- retrieval-provider §6 — `RerankResponse` / `ScoredDocument` / `RerankUsage` shapes and the
  sort + valid-index cross-impl invariants.

**Cases:**

1. `rerank_response_shape_invariants_satisfied` — 3 documents; mock returns scores `[0.5, 0.9, 0.1]`
   for input indices `[0, 1, 2]` (unsorted). The adapter MUST return results sorted descending —
   scores `[0.9, 0.5, 0.1]`, indices `[1, 0, 2]` — with `usage.search_units = 1`,
   `usage.input_tokens = null`, and `response_id = "rerank-006-id"`.

**What passes:**

- Results sorted by `relevance_score` descending with input `index` preserved per entry.
- `usage` and `response_id` populated from the provider response.

**What fails:**

- Results returned in provider order without the adapter-side sort.
- `index` rewritten to the sorted position (losing the input-documents mapping).
- `usage.search_units` dropped or `input_tokens` fabricated when the provider omitted it.
