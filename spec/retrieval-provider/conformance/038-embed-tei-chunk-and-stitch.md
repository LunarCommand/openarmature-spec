# 038 — TEI `/embed` mandatory batch chunking (`max-client-batch-size` cap, load-bearing)

The **second** embedding chunk-and-stitch fixture (after Cohere 037), proving the general
retrieval-provider §8 *Batch chunking* rule **generalizes across mappings**. Verifies the rule on the TEI
`/embed` mapping (§8.1): when a caller's input list exceeds the provider's per-call input cap, the mapping
MUST split the inputs into consecutive `≤ cap` slices (preserving order), issue one `/embed` request per
chunk with identical per-call params, concatenate the per-chunk vectors **in input order**, and combine the
per-chunk usage — sum `EmbeddingUsage.input_tokens` when the provider reports usage, or produce
`usage = null` when it reports none; `EmbeddingResponse.response_id` is the **first** chunk's response
id. A mapping MUST NOT silently send an over-cap request.

Where 037 exercised this rule on Cohere's **fixed vendor cap** (96), this fixture exercises it on TEI
`/embed`, whose cap is the genuinely **configurable** `max-client-batch-size` — surfaced as the
construction `chunk_size` (§8.1 `/embed`: "bounded by TEI's `max-client-batch-size` (the construction
`chunk_size`); an over-cap embed call chunk-and-stitches per the §8 *Batch chunking* rule"). A small
`chunk_size` is therefore realistic, not synthetic. It also fills a gap: TEI's existing chunk fixture
(015) covers `/rerank` only, not `/embed`.

**Spec sections exercised:**

- retrieval-provider §8 — *Batch chunking* (the general rule): consecutive `≤ cap` slices, one request per
  chunk with identical per-call params, vectors concatenated in input order, usage combined record-aware
  (`input_tokens` summed when usage is reported, else `usage = null`), `response_id` from the first chunk;
  a mapping MUST NOT send an over-cap request.
- retrieval-provider §8.1 TEI — `/embed`: `POST {base_url}/embed` with `{"inputs": [str]}` (always the
  array form), bounded by `max-client-batch-size` / the construction `chunk_size`; the response is the
  **bare** vector array in input order; TEI surfaces no usage and no response id.
- retrieval-provider §3 / §4 — input-order preservation; the §4 one-vector-per-input and
  uniform-dimensionality invariants enforced against the **stitched** result.

**Case:**

1. `five_inputs_three_chunks_stitched_in_input_order` — 5 inputs, construction `chunk_size: 2`. The
   mapping issues exactly THREE `/embed` requests with `inputs` sizes `[2, 2, 1]` over the consecutive
   slices `input[0:2]`, `input[2:4]`, `input[4:5]`, with identical per-call params on each — the bare array
   form `{"inputs": [...]}` with **no** `prompt_name` and **no** `dimensions` (no `input_type` and no
   config supplied). Each chunk's mocked TEI response is the bare vector array for that chunk (dimension 2;
   first component == the absolute input index / 10, `0.0` … `0.4`). The adapter MUST stitch: concatenate
   the per-chunk vectors **in input order** (5 vectors, vector `i` == the embedding for input `i` across
   the chunk boundaries). `EmbeddingResponse.model` is the bound id (TEI echoes none).

**§8 facets exercised here vs. deferred to 037:** this fixture exercises consecutive `≤ chunk_size`
chunking, the request count, identical per-call params across chunks, vectors stitched **in input order**,
and the MUST-NOT-send-over-cap rule. TEI `/embed` carries no usage object (017), so the stitched
`EmbeddingResponse.usage` is `null`: §4 makes `usage` a `record | null` and maps TEI `/embed` to
`usage = null`, and §8's batch-chunking step 4 sums `input_tokens` when the provider reports usage or
produces `usage = null` when it reports none — TEI reports none. This fixture therefore asserts
`usage: null` (consistent with §4 and with 017). The §8 sum-`input_tokens` branch is exercised by the
Cohere instance (037), whose `/v2/embed` reports `meta.billed_units` and sums to `500`. TEI also surfaces
no response id, so the §8 "first chunk's id" ⇒ **`null`** (matching 017).

**What passes:**

- Exactly three `/embed` requests with `inputs` sizes `[2, 2, 1]`, consecutive slices, identical per-call
  params on each (bare array form; `prompt_name` and `dimensions` absent on every chunk).
- The stitched `vectors` are the per-chunk bare vector arrays concatenated in input order (one vector per
  input, all of equal dimensionality, `dimensions` field equal to the inner-vector length).
  `expected.final_state` pins the concrete 5-element `vectors` array (chunk-A `[0:2]`, chunk-B `[2:4]`,
  chunk-C `[4:5]`), so a permuting or boundary-swapped stitch fails on the data itself, not only on the
  named order invariant.
- `EmbeddingResponse.model` is the bound id; `response_id` is `null` (TEI surfaces none —
  first-of-no-ids). `usage` is `null` (TEI `/embed` carries no usage object; §8 step 4 produces
  `usage = null` when the provider reports none — see above).

**What fails:**

- An un-chunked single over-cap request (chunking is mandatory, not optional), a wrong chunk count, or
  non-consecutive / wrong-sized slices.
- A mis-ordered stitch (the distinct per-index first component surfaces a wrong vector at a chunk
  boundary).
- Per-call params drifting across chunks, or a `prompt_name` / `dimensions` param leaked onto any chunk
  request.
- A `response_id` invented where TEI's bare-array `/embed` surfaces none.
