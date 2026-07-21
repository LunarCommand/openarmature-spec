# 043 — OpenAI-compatible `/v1/embeddings` mandatory batch chunking (§8.3, 2048-input cap)

The **first §8.3 OpenAI** embedding chunk-and-stitch fixture (embedding chunk-and-stitch is also exercised by
Cohere 037, TEI 038, and Cohere 042), closing the §8.3 OpenAI coverage hole: before this, an implementation
could ship the §8.3 mapping sending an over-cap `input` list **un-chunked** and still pass the whole retrieval
suite — 037 covers Cohere's cap, 038 covers TEI's, and neither drives the OpenAI mapping. Verifies the retrieval-provider §8 *Batch chunking* rule on the §8.3
OpenAI-compatible `/v1/embeddings` mapping: when a caller's input list exceeds the provider's per-call input
cap, the mapping MUST split the inputs into consecutive `≤ cap` slices (preserving order), issue one
`/v1/embeddings` request per chunk with identical per-call params, concatenate the per-chunk vectors **in
input order**, and combine the per-chunk usage — sum `EmbeddingUsage.input_tokens` when the provider reports
usage; `EmbeddingResponse.response_id` is the **first** chunk's response id. A mapping MUST NOT silently
send an over-cap request.

**Cap override (test-only).** §8.3's OpenAI cap is a **fixed vendor limit** of 2048 inputs — **not**
construction-configurable, unlike TEI's genuinely configurable `max-client-batch-size` (038's real
`chunk_size`). A faithful over-cap body would need 2049 inputs, which is not reviewable in a fixture. So this
fixture supplies `chunk_size: 2` on the `openai_embedding_provider` construction block via the
**conformance-adapter `chunk_size` directive** ([conformance-adapter §5.14](../../conformance-adapter/spec.md)),
which an adapter **MUST** honor as the provider's per-call input cap — here a test-only override of the fixed
cap, exercising the chunking path with a small body. The real §8.3 mapping's cap stays 2048. (037 did not need
this — Cohere's fixed 96 is small enough to test with a real 100-input body; OpenAI's 2048 is not.)

**Spec sections exercised:**

- retrieval-provider §8 — *Batch chunking* (the general rule): consecutive `≤ cap` slices, one request per
  chunk with identical per-call params, vectors concatenated in input order, usage combined record-aware
  (`input_tokens` **summed** when usage is reported), `response_id` from the first chunk; a mapping MUST NOT
  send an over-cap request. The §8 `raw` stitch clause sets `EmbeddingResponse.raw` to the **list of the
  per-chunk verbatim responses**, in request order — here a list of response **objects** (the `{object,
  data, model, usage}` dicts), one level deeper than a single-request `raw`, NOT flattened into `vectors`.
- retrieval-provider §8.3 OpenAI — `/v1/embeddings`: `POST {base_url}/v1/embeddings` with `{"model",
  "input": [str]}` (always the array form), a fixed 2048-input cap; the `{object, data: [{object, index,
  embedding}], model, usage}` response mapping onto vectors in input order; `usage.prompt_tokens →
  EmbeddingUsage.input_tokens`; OpenAI embeddings carry no top-level id.
- retrieval-provider §3 / §4 — input-order preservation; the §4 one-vector-per-input and
  uniform-dimensionality invariants enforced against the **stitched** result.

**Cases:**

1. `five_inputs_three_chunks_summed_usage_stitched_in_input_order` — 5 inputs, test-override `chunk_size: 2`
   (standing in for §8.3's fixed 2048 cap). The mapping issues exactly THREE `/v1/embeddings` requests with
   `input` sizes `[2, 2, 1]` over the consecutive slices `input[0:2]`, `input[2:4]`, `input[4:5]`, with
   identical per-call params on each — `{"model": "text-embedding-test", "input": [...]}` with **no**
   `dimensions`, **no** `encoding_format`, **no** `input_type` (no config supplied; the OpenAI wire has no
   query/document field). Each chunk's mocked OpenAI response is the `{object, data, model, usage}` shape
   with `data` emitted **out of** within-chunk order (index 1 before 0) so an adapter trusting array
   position produces the wrong mapping at a chunk boundary; each embedding's first component == the absolute
   input index / 10 (`0.0` … `0.4`). The adapter MUST stitch: concatenate the per-chunk vectors **in input
   order** (5 vectors, vector `i` == the embedding for input `i` across the chunk boundaries).
2. `over_token_chunk_fails_loud_no_partial_stitch` — the **count-vs-token boundary**. 3 inputs,
   `chunk_size: 2`, so count-chunking splits into `[2, 1]` — chunk A `[e0, e1]`, chunk B a single very long
   input. Chunk A returns `200`; chunk B's lone input exceeds OpenAI's per-request **summed-token ceiling**,
   so OpenAI returns `400`. The §8 rule chunks by input **count** only, so chunk B is **not** sub-chunked by
   an estimated token count (it is already a single input, and OA performs no client-side token estimation).
   The `400` maps to `provider_invalid_request` (§7) and the **whole call fails loud**: no partial stitch of
   chunk A's vectors, no `EmbeddingResponse` stored. Both chunk requests reach the wire (count-chunking
   happened) before the call raises. This closes the **mid-chunk-failure** coverage gap — no prior fixture
   drove a chunk-and-stitch call in which one chunk fails. Because chunk B is a single input, it cannot be
   token-sub-chunked either way, so case 2 alone does *not* discriminate a token-estimating sub-chunker —
   case 3 does.
3. `multi_input_over_token_chunk_sent_whole_not_token_sub_chunked` — the **discriminating** case. 2 inputs,
   `chunk_size: 2`, so count-chunking produces a **single** chunk of both (2 ≤ cap; no over-cap chunking).
   Each input is individually under the per-request token ceiling, but their **summed** tokens exceed it, so
   OpenAI returns `400` on that one request. A conforming §8.3 mapping — count-chunking only, **no** token
   estimation — sends both inputs as **one** request, gets the `400`, and fails loud. A non-conforming
   token-sub-chunker would split the multi-input over-token chunk into two under-ceiling single-input
   requests, get two `200`s, and wrongly return a stitched result — issuing **two** requests and **not**
   raising. So `expected_wire_request_count: 1` plus the fail-loud outcome together fail any token-estimating
   sub-chunker. This is what actually pins the §8.3 "no client-side token estimation" MUST that case 2, with
   its un-splittable single-input chunk, cannot.

**What 043 adds over 037 / 038.** OpenAI `/v1/embeddings` **reports** usage, so this is the **first §8.3**
fixture to exercise §8 step 4's **sum-`input_tokens`** branch (037 and 042 also sum Cohere's `billed_units`;
038 is the `usage = null` branch): per-chunk `prompt_tokens` `10 + 20 + 5` sum to `input_tokens 35` — values
chosen distinct from the chunk sizes `[2, 2, 1]` and their sum from the input count `5`, so the summation is
load-bearing. The chunk-and-stitch `raw` here is a **list of per-chunk response objects** (the `{object, data,
model, usage}` dicts) — distinct from 038's list of bare vector arrays — exercising the object-shaped chunked
`raw`. OpenAI embeddings carry no top-level id, so the §8 "first chunk's id" is `null` (like TEI 038, unlike
Cohere 037).

**What passes:**

- Exactly three `/v1/embeddings` requests with `input` sizes `[2, 2, 1]`, consecutive slices, identical
  per-call params on each (`model` present; `dimensions`, `encoding_format`, `input_type` absent on every
  chunk), and the `Authorization: Bearer` header on each.
- The stitched `vectors` are the per-chunk vectors concatenated in input order (one vector per input, all of
  equal dimensionality, `dimensions` field equal to the inner-vector length). `expected.final_state` pins
  the concrete 5-element `vectors` array, so a permuting or boundary-swapped stitch fails on the data itself.
- `EmbeddingResponse.model` is the bound id; `response_id` is `null` (OpenAI surfaces none); `usage.input_tokens`
  is `5` (the per-chunk `prompt_tokens` **summed**).
- `raw` is the list of the three per-chunk verbatim response **objects** in request order (each `data` in its
  emitted order, not re-sorted) — the chunk responses unstitched, not the flattened `vectors`.

**What fails:**

- An un-chunked single over-cap request (chunking is mandatory, not optional), a wrong chunk count, or
  non-consecutive / wrong-sized slices.
- A mis-ordered stitch (the distinct per-index first component surfaces a wrong vector at a chunk boundary).
- Per-call params drifting across chunks, or a `dimensions` / `encoding_format` param leaked onto any chunk
  request.
- Usage summed wrong (anything other than `5`), a `response_id` invented where OpenAI surfaces none, or `raw`
  flattened / first-chunk-only instead of the list of per-chunk response objects.
