# 023 — OpenAI-compatible `/v1/embeddings` wire round-trip

Verifies the retrieval-provider §8.3 OpenAI-compatible embedding mapping on the request and response
wire surfaces — the de-facto-standard `/v1/embeddings` wire, the **third** §8 mapping after TEI's
`/embed` (017) and Jina's `/v1/embeddings` (020). An OpenAI-compatible `EmbeddingProvider` MUST POST the
array-form request to `{base_url}/v1/embeddings` with `Authorization: Bearer <key>`, and consume the
`{object, data, model, usage}` response into `EmbeddingResponse` vectors **in input order**.

**Spec sections exercised:**

- retrieval-provider §3 — `embed()` MUST preserve input order (vector at index `i` is the embedding of
  `input[i]`); the request always sends the array form even for a single-string caller ("always a
  list").
- retrieval-provider §4 — `EmbeddingResponse` / `EmbeddingUsage` shapes: `vectors` length == `input`
  length, all inner vectors same dimensionality, `dimensions` field == inner length, `response_id` null
  when the provider returns none.
- retrieval-provider §8.3 OpenAI-compatible embeddings — *Construction*: API key sent as
  `Authorization: Bearer <key>`; `base_url` origin-only, mapping appends `/v1/embeddings`.
  `/v1/embeddings` request `{model, input: [str], dimensions?, encoding_format?}`; response
  `{object, data: [{object, index, embedding}], model, usage: {prompt_tokens, total_tokens}}` →
  vectors in input order; `usage.prompt_tokens` → `EmbeddingUsage.input_tokens` (`total_tokens` ==
  `prompt_tokens`).

**Cases:**

1. `embed_array_form_response_in_input_order` — `embed()` over 3 inputs, no config. The wire request
   MUST be exactly `{model, input: [s0, s1, s2]}` (array form, no `dimensions` / `encoding_format` /
   `input_type` / `task`) with `Authorization: Bearer` present. The mocked response emits `data` **out
   of order** (index 2, 0, 1); the adapter MUST return vectors in **input** order, with `vectors`
   length 3, all inner length 4, `dimensions` 4, model echoed, `response_id` null, and
   `usage.prompt_tokens` 6 → `usage.input_tokens` 6.

**What passes:**

- The wire body is the array form `{model, input}` and carries the `Authorization: Bearer <api_key>`
  header.
- The response `data` entries assemble to `EmbeddingResponse.vectors` keyed by **input order** (not
  array position) — distinct first components and out-of-order `data` make this load-bearing.
- `usage.prompt_tokens` → `input_tokens`; `response_id` is null (OpenAI embeddings carry no id).

**What fails:**

- The request is sent as a bare string rather than the array form, or omits `model` / the
  `Authorization: Bearer` header.
- Vectors are mapped by `data` array position instead of input order (the out-of-order `data` would
  surface this).
- `usage.prompt_tokens` dropped, or a non-null `response_id` fabricated when OpenAI returns none.
