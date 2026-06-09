# 001 — `EmbeddingProvider.embed()` positive control

Verifies retrieval-provider §3 (`embed()` operation contract) and §4 (`EmbeddingResponse` /
`EmbeddingUsage` shapes and cross-impl invariants) on a successful call.

**Spec sections exercised:**

- retrieval-provider §3 — `EmbeddingProvider.embed()` operation contract.
- retrieval-provider §4 — `EmbeddingResponse` and `EmbeddingUsage` shapes; cross-impl invariants
  (vector count matches input count, all vectors same dimensionality, dimensions field equals
  inner-vector length).

**Cases:**

1. `embed_response_shape_invariants_satisfied` — Mocked OpenAI-compatible `/v1/embeddings`
   response returns 3 vectors of dimension 4 for 3 input strings, with `usage.prompt_tokens=6`
   and `id="emb-001-id"`. Asserts the response carries `vectors` of length 3, all inner vectors
   of length 4, `dimensions=4`, `usage.input_tokens=6`, `model="text-embedding-test"`, and
   `response_id="emb-001-id"`.

**What passes:**

- The response record matches all expected field values.
- Cross-impl invariants hold (vector count, dimensionality consistency, dimensions field
  accuracy).

**What fails:**

- The response permutes vectors (would violate input-order preservation per §3; covered by
  fixture 005).
- The `dimensions` field disagrees with the inner-vector length — cross-check invariant broken.
- `response_id` is missing when the provider returned one — adapter dropped the field.
- `usage.input_tokens` is null when the provider returned a usage record — adapter dropped the
  usage record.
