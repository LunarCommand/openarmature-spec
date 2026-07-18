# 042 — Cohere `/v2/embed` chunk-and-stitch: malformed per-chunk usage and first-chunk id are *not reported*

Verifies the chunk-and-stitch interaction of retrieval-provider §7 *Malformed ancillary figures* with §8
*Batch chunking* step 4 on the §8.4 Cohere **embedding** mapping. An over-cap (`> 96` inputs) embed call
chunk-and-stitches across two `/v2/embed` requests. Two branches of §8 step 4 are pinned:

- **Usage collapse** (case 1): **one** chunk's `meta.billed_units.input_tokens` is **malformed** and the
  other's is sound. Per §8 step 4 (amended by §7): a chunk whose `input_tokens` is malformed has **not
  reported** usage, so if **any** chunk is malformed the stitched `EmbeddingResponse.usage` is `null`. A
  mapping **MUST NOT** sum only the well-formed chunks — that reports a total the provider never sent,
  understating the true count and indistinguishable from a truthful figure — the fabrication §7 forbids.
- **First-chunk id, no fall-through** (case 2): both chunks report **sound** `input_tokens`, but the
  **first** chunk's top-level `id` is **malformed**. Per §8 step 4, `response_id` is the first chunk's id
  and a malformed first-chunk id is `null` — a mapping **MUST NOT** fall through to a later chunk's id. The
  summed `usage` is unaffected, judged independently of the id.

Nothing is lost: `raw` is the **list** of the per-chunk verbatim responses (§8 / 0096), so every chunk's
figure — including the malformed one — remains available. The vectors stitch normally (the malformed
accounting / id figure does not impugn the payload), and the rule binds the **typed event** (graph-engine
§6): `EmbeddingEvent` MUST mirror the stitched response's nulled figure.

These are the chunk-and-stitch analogues of fixture 040 Case A's single-request single-figure collapse
(case 1) and Case B's malformed-numeric-id null (case 2), resting on fixture 037's mandatory 96-input-cap
chunk-and-stitch structure (100 inputs → chunks `[96, 4]`).

**Spec sections exercised:**

- retrieval-provider §8 *Batch chunking* step 4 (amended by §7) — a malformed per-chunk `input_tokens` means
  that chunk has not reported usage, so the stitched `usage` is `null`; a mapping MUST NOT sum only the
  well-formed chunks. `EmbeddingResponse.response_id` is the **first** chunk's id; a malformed first-chunk id
  is `null` and a mapping MUST NOT fall through to a later chunk's id. `EmbeddingResponse.raw` is the list of
  the per-chunk verbatim response objects, in request order.
- retrieval-provider §7 *Malformed ancillary figures* — the not-reported / no-fabrication / verbatim-on-`raw`
  rule; binds the typed `EmbeddingEvent` (graph-engine §6).
- retrieval-provider §8.4 Cohere — *Mandatory batch chunking (96-input cap)*: consecutive `≤ 96` slices, one
  request per chunk with identical per-call params, vectors concatenated in input order.
- retrieval-provider §3 / §4 — input-order preservation and the one-vector-per-input / uniform-dimensionality
  invariants enforced against the **stitched** result.

**Cases:**

1. `malformed_chunk_input_tokens_collapses_stitched_usage_to_null` — 100 inputs, Cohere's 96-input cap. The
   mapping issues exactly TWO `/v2/embed` requests with `texts` sizes `[96, 4]` over the consecutive slices
   `input[0:96]`, `input[96:100]`, identical per-call params on each. Chunk A reports a **sound**
   `input_tokens` `480`; chunk B reports a **malformed** `input_tokens` (the string `"abc"`). The adapter
   stitches the vectors in input order (100 vectors, each first component the absolute input index / 1000),
   takes `response_id` from the first chunk's id, and — because chunk B has not reported usage — sets the
   stitched `usage` to `null` (**not** `480`, a partial sum of only chunk A). No raise. `raw` is the list of
   the two per-chunk verbatim response objects (chunk A's `480`-token object, chunk B's malformed-`"abc"`
   object). `EmbeddingEvent.usage` is `null`.
2. `malformed_first_chunk_id_nulls_response_id_no_fall_through` — same 100-input over-cap call, `texts` sizes
   `[96, 4]`. This time **both** chunks report **sound** `input_tokens` — chunk A `480`, chunk B `20` — so
   the stitched `usage` is the real summed record `{input_tokens: 500}` (§8's sum rule). What is malformed is
   the **first** chunk's top-level `id`: chunk A carries the **number** `99999` where a string id belongs
   (fixture 040 Case B's malformed-id kind), while chunk B (a **later** chunk) carries a **sound** string id
   (`cohere-embed-042b-chunkB-id`). `EmbeddingResponse.response_id` is `null` — the first chunk's id is
   malformed and a mapping MUST NOT fall through to a later chunk's id, so it is **not** chunk B's sound id
   and **not** the stringified `"99999"`. The summed `usage` stands (judged independently), the vectors
   stitch in input order, no raise. `raw` is the list of both per-chunk verbatim objects (chunk A carrying
   the numeric `99999`, chunk B its sound string id). `EmbeddingEvent.response_id` is `null`;
   `EmbeddingEvent.usage` is `{input_tokens: 500}`.

**What passes:**

- Exactly two `/v2/embed` requests with `texts` sizes `[96, 4]`, consecutive slices, identical per-call
  params on each (no `output_dimension` on either); the `Authorization: Bearer` header present.
- The stitched `vectors` are the per-chunk `embeddings.float` arrays concatenated in input order (the
  concrete 100-element array is pinned, so a permuting or boundary-swapped stitch fails on the data itself);
  one vector per input; uniform dimensionality; `dimensions` equal to the inner-vector length.
- No `provider_invalid_response` is raised in either case — the malformed accounting / id figure does not
  impugn the payload.
- Case 1: `response_id` taken from the first chunk's sound id (`cohere-embed-042-chunk-a-id`); the stitched
  `usage` is `null` — a malformed chunk means unreported usage, so the whole stitched figure is not reported
  (**not** `480`, **not** `484`, **not** `0`); `raw` is the list of both objects with chunk B's malformed
  `"abc"` preserved byte-for-value; `EmbeddingEvent.usage` is `null`.
- Case 2: `response_id` is `null` — the **first** chunk's id is the malformed number `99999`, and a mapping
  MUST NOT fall through to a later chunk's id, so it is **not** chunk B's sound id
  (`cohere-embed-042b-chunkB-id`) and **not** the stringified `"99999"`. The stitched `usage` is the summed
  record `{input_tokens: 500}` (`480 + 20`), unaffected by the id defect. `raw` is the list of both objects,
  with chunk A's numeric `99999` preserved byte-for-value; `EmbeddingEvent.response_id` is `null` and
  `EmbeddingEvent.usage` is `{input_tokens: 500}`.

**What fails:**

- Summing only the well-formed chunks into `480` (or coercing / dropping `"abc"` to reach any non-null
  total) — the fabrication §7 forbids (case 1).
- **Falling through to a later chunk's id**: surfacing chunk B's sound `cohere-embed-042b-chunkB-id` as
  `response_id` when the first chunk's id is malformed — the discriminating failure of case 2 (a "use the
  first non-malformed chunk id" bug passes every other assertion but fails here). Also stringifying `99999`
  to `"99999"`.
- Letting the malformed first-chunk id disturb the summed `usage` (case 2 — it MUST stay `{input_tokens:
  500}`), or letting a malformed usage figure disturb the sound sibling.
- Raising `provider_invalid_response` over a malformed per-chunk figure or id.
- A mis-ordered stitch (the distinct per-index first component surfaces a wrong vector at the chunk
  boundary), a wrong chunk count, or non-consecutive / wrong-sized slices.
- `response_id` taken from the second chunk's id instead of the first (case 1).
- Surfacing a nulled figure as non-null on the `EmbeddingEvent` (`usage` in case 1, `response_id` in case
  2), or collapsing the chunked `raw` list into a single merged object / dropping either chunk's verbatim
  value from `raw`.
