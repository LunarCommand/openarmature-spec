# 041 — Cohere `/v2/rerank` malformed usage figure is *not reported*

Verifies retrieval-provider §7 *Malformed ancillary figures* on the §8.4 Cohere **rerank** mapping: the
reranking is sound but the single reported usage figure is **malformed**. The call **succeeds** — the
results are sorted and intact, no §7 category is raised — the figure is **nulled** (never fabricated,
coerced, clamped, or repaired), and the verbatim malformed value stays on `raw` (§6). The rule binds the
**typed event** (graph-engine §6): `RerankEvent.usage` MUST be `null` to match the response.

Cohere `/v2/rerank` meters **only** `meta.billed_units.search_units` → `RerankUsage.search_units` and never
reports `input_tokens` (§8.4 — the inverse of Jina §8.2). So the reported figure set is a single figure; a
malformed `search_units` is not reported, and with `input_tokens` already unreported no figure is reported,
which collapses `RerankResponse.usage` to `null` (§6 — "a record is present when at least one figure is
reported").

**Reachability note.** No current rerank mapping surfaces **both** usage figures on the same wire — Cohere
reports `search_units` only, Jina `input_tokens` only, TEI none — so a **partial record** where one figure
is malformed and the *other* survives is not constructible against any real mapping. Each mapping's single
reported figure collapses the record just as embedding's single-figure `EmbeddingUsage` does (fixture 040
Case A). The two-figure partial record is a consequence of §7's per-figure rule that the rule **states** but
no mapping can exercise yet; this fixture pins the reachable single-figure collapse.

**Spec sections exercised:**

- retrieval-provider §7 *Malformed ancillary figures* — a malformed ancillary figure MUST NOT raise, MUST
  NOT be fabricated / coerced / clamped / repaired, MUST remain verbatim on `raw`, and is nulled per §6's
  record rules. Binds the typed `RerankEvent` (graph-engine §6).
- retrieval-provider §5 / §6 — `rerank()` MUST sort by `relevance_score` descending with each `index` valid
  into the input; `RerankUsage` is present only when at least one figure is reported; `raw` is the verbatim
  response.
- retrieval-provider §8.4 Cohere — the `/v2/rerank` mapping (unchanged from 028): `meta.billed_units.search_units`
  → `RerankUsage.search_units`, `input_tokens` never reported; Cohere echoes no document, so every
  `ScoredDocument.document` is `null`; top-level `id` → `response_id`; `model` is the bound id.

**Case:**

1. `malformed_search_units_collapses_usage_to_null` — 3 documents, default config, no `top_k`. The mocked
   Cohere response is **unsorted** with sound results and a sound top-level `id`, but
   `meta.billed_units.search_units` is the negative `-3`. `RerankResponse.usage` collapses to `null`
   (Cohere's only reported figure is malformed); results sorted descending with valid indices; every
   `document` `null`; no raise; the verbatim `-3` preserved on `raw`; `RerankEvent.usage` is `null`.

**What passes:**

- Exactly one `/v2/rerank` request; the request wire shape unchanged from 028 (`model`, `query`,
  `documents` string array; no `top_n` / `return_documents` / `truncation`).
- Results sorted by `relevance_score` descending (`[{1, 0.91}, {0, 0.42}, {2, 0.08}]`) with each `index`
  valid into the 3-document input; every `document` `null` (Cohere echoes none).
- `usage` is `null` — the single reported figure (`search_units`) is malformed, so no figure is reported and
  the whole record collapses; NOT `{search_units: 0, input_tokens: null}` and NOT `{search_units: -3, ...}`.
- No `provider_invalid_response` (or any §7 category) is raised.
- The verbatim `-3` is preserved byte-for-value on `raw`; `RerankEvent.usage` is `null`.

**What fails:**

- Raising `provider_invalid_response` over the malformed usage figure (discarding a valid ranking).
- Clamping `-3` to `0`, or fabricating any `search_units` value.
- Returning results in provider order without the sort, or an `index` rewritten to the sorted position.
- Surfacing the malformed figure on `RerankEvent.usage` while the response reports it as absent.
- Dropping the verbatim `-3` from `raw`, or fabricating a `document` from the input list.
