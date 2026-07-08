# 037 — Cohere `/v2/embed` mandatory batch chunking (96-input cap, load-bearing)

The load-bearing fixture for the retrieval-provider §8.4 Cohere **embed** chunk-and-stitch contract.
Verifies *Mandatory batch chunking (96-input cap)*: Cohere `/v2/embed` accepts at most 96 inputs per
request, so when `len(input)` exceeds 96 the mapping MUST split the inputs into consecutive `≤ 96` chunks,
issue one `/v2/embed` request per chunk (identical per-call params), concatenate the per-chunk
`embeddings.float` arrays **in input order**, and sum `meta.billed_units.input_tokens` across chunks into
`EmbeddingUsage.input_tokens`; `EmbeddingResponse.response_id` is the **first** chunk's `id`. The embedding
analogue of §8.1's rerank chunk-and-stitch (fixture 015), resting on the same per-input-independence
property — applied here to a **fixed vendor cap** (96), not TEI's construction-configured `chunk_size`.

**Spec sections exercised:**

- retrieval-provider §8.4 Cohere — *Mandatory batch chunking (96-input cap)*: consecutive `≤ 96` slices,
  one request per chunk with identical `model` / `input_type` / `embedding_types` / `truncate` /
  `output_dimension`, vectors concatenated in input order, `input_tokens` summed, `response_id` from the
  first chunk; a mapping MUST NOT silently send an over-cap request. The §8 `raw` stitch clause sets `EmbeddingResponse.raw`
  to the **list of the per-chunk verbatim response objects**, in request order — proving an
  object-response chunked `raw` is a list-of-objects, not a single merged object.
- retrieval-provider §3 / §4 — input-order preservation; the §4 one-vector-per-input and
  uniform-dimensionality invariants enforced against the **stitched** result.

**Case:**

1. `hundred_inputs_two_chunks_stitched_in_input_order` — 100 inputs, Cohere's 96-input cap. The mapping
   issues exactly TWO `/v2/embed` requests with `texts` sizes `[96, 4]` over the consecutive slices
   `input[0:96]`, `input[96:100]`, with identical per-call params on each (`model: cohere-embed-test`,
   `input_type: "search_document"` — the mandatory default since no OA `input_type` was supplied,
   `embedding_types: ["float"]`, `truncate: "NONE"`, and **no** `output_dimension`). Each chunk's mocked
   response carries that chunk's inputs' vectors under `embeddings.float`, with each vector's first
   component equal to its **absolute** input index / 1000 (`0.000` … `0.099`). The adapter MUST stitch:
   concatenate the per-chunk vectors **in input order** (100 vectors, vector `i` == the embedding for input
   `i` across the chunk boundary), sum `input_tokens` `480 + 20` → `500`, and take `response_id` from the
   **first** chunk's `id` (`cohere-embed-037-chunk-a-id`; chunk B's `id` differs).
   `EmbeddingResponse.model` is the bound id (Cohere echoes none).

**What passes:**

- Exactly two `/v2/embed` requests with `texts` sizes `[96, 4]`, consecutive slices, identical per-call
  params on each (no `output_dimension` on either); the `Authorization: Bearer` header present.
- The stitched `vectors` are the per-chunk `embeddings.float` arrays concatenated in input order (one
  vector per input, all of equal dimensionality, `dimensions` field equal to the inner-vector length).
  `expected.final_state` pins the concrete 100-element `vectors` array (chunk-A floats `[0:96]` then
  chunk-B floats `[96:100]`), so a permuting or boundary-swapped stitch fails on the data itself, not only
  on the named order invariant.
- `input_tokens` summed across chunks (`500`); `response_id` taken from the first chunk's `id`;
  `EmbeddingResponse.model` the bound id.
- `raw` is the list of the two per-chunk Cohere `{id, embeddings, meta}` response objects verbatim, in
  request order (chunk A's 96-vector object, then chunk B's 4-vector object) — a list-of-objects, not a
  single merged object, and distinct from the stitched `vectors` / summed `usage`.

**What fails:**

- An un-chunked single over-cap request (chunking is mandatory, not optional), a wrong chunk count, or
  non-consecutive / wrong-sized slices.
- A mis-ordered stitch (the distinct per-index first component surfaces a wrong vector at the chunk
  boundary).
- `input_tokens` taken from a single chunk instead of summed; `response_id` taken from the second chunk's
  `id` (or fabricated) instead of the first chunk's.
- Per-call params drifting across chunks (different `input_type` / `embedding_types` / `truncate`, or an
  `output_dimension` on one chunk but not the other).
