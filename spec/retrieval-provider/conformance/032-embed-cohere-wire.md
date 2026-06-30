# 032 — Cohere `/v2/embed` wire round-trip

Verifies the retrieval-provider §8.4 Cohere **embedding** mapping on the `/v2/embed` request and response
wire surfaces — §8.4's embed half, the companion to 028's `/v2/rerank` round-trip (the second endpoint on
the same vendor section, the §8.2 Jina embed+rerank pattern). The request carries `{model, input_type,
texts, embedding_types: ["float"], truncate: "NONE"}` with the `Authorization: Bearer <api_key>` header
and **no** `output_dimension`; the Cohere response maps onto §4's `EmbeddingResponse` with `embeddings.float`
assembled in input order, `meta.billed_units.input_tokens` → `EmbeddingUsage.input_tokens`, and the
top-level `id` → `response_id`. The input_type realization is fixture 033; `output_dimension` is 035; the
`truncate: "NONE"` fail-loud path is 036; the 96-input chunk-and-stitch is 037.

**Spec sections exercised:**

- retrieval-provider §3 / §4 — `embed()` MUST preserve input order; `EmbeddingResponse` / `EmbeddingUsage`
  shapes and cross-impl invariants (one vector per input, uniform dimensionality, `dimensions` field
  equals inner-vector length).
- retrieval-provider §8.4 Cohere — *Construction*: the provider binds an API key sent as
  `Authorization: Bearer <key>`. `/v2/embed` request shape `{model, input_type, texts: [str],
  embedding_types: ["float"], truncate: "NONE", output_dimension?}`; `texts` ← the input strings (array
  form); `input_type` is a **mandatory wire field** — with no OA `input_type` the mapping sends the
  `search_document` default (the bulk-indexing default; see 033). The response `{id, embeddings: {float:
  [[...]]}, texts, meta: {billed_units: {input_tokens}}}` maps onto §4: `embeddings.float` → vectors in
  input order; `meta.billed_units.input_tokens` → `EmbeddingUsage.input_tokens`; top-level `id` →
  `response_id`. Cohere's embed response echoes no `model` field, so `EmbeddingResponse.model` is the bound
  model identifier.

**Cases:**

1. `embed_wire_round_trip_input_order` — 2 inputs `["alpha", "beta"]`, default config. Exactly ONE POST to
   `{base_url}/v2/embed` carrying `{model, input_type: "search_document", texts: ["alpha", "beta"],
   embedding_types: ["float"], truncate: "NONE"}` with `output_dimension` ABSENT and the
   `Authorization: Bearer <api_key>` header present. The mocked Cohere response carries `embeddings.float`
   as two 4-d vectors; the adapter MUST assemble `vectors` from `embeddings.float` **in input order**.
   `meta.billed_units.input_tokens` 6 → `EmbeddingUsage.input_tokens` 6; top-level `id` → `response_id`;
   `EmbeddingResponse.model` is the bound id `cohere-embed-test` (Cohere echoes none).

**What passes:**

- Exactly one `/v2/embed` request; `model` + `texts` (string array, in order) on the body;
  `embedding_types: ["float"]` and `truncate: "NONE"` present; `output_dimension` absent (no `dimensions`
  supplied).
- `input_type` is `"search_document"` (the mandatory-field default when no OA `input_type` is supplied).
- The `Authorization: Bearer <api_key>` header is present on the outbound request.
- `vectors` assembled from `embeddings.float` in input order; one vector per input; all vectors of equal
  dimensionality; `dimensions` field equals the inner-vector length.
- `meta.billed_units.input_tokens` → `input_tokens`; top-level `id` → `response_id`;
  `EmbeddingResponse.model` is the bound id (Cohere echoes none).

**What fails:**

- More than one request issued; `texts` reordered; `model` omitted; `embedding_types` or `truncate`
  omitted; `output_dimension` emitted when no `dimensions` was supplied.
- `input_type` omitted from the wire (Cohere requires it) or sent as something other than `search_document`
  for the absent-OA-`input_type` case.
- The `Authorization: Bearer` header missing or carrying the wrong scheme.
- Vectors read from a top-level `data` array (the OpenAI shape) instead of `embeddings.float`, or permuted
  relative to input order.
- `input_tokens` dropped, `response_id` not sourced from the top-level `id`, or `model` fabricated /
  left null instead of falling back to the bound identifier.
