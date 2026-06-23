# 024 — OpenAI-compatible `/v1/embeddings` `dimensions` passthrough

Verifies the retrieval-provider §8.3 OpenAI-compatible embedding mapping passes
`EmbeddingRuntimeConfig.dimensions` onto the wire `dimensions` field (Matryoshka, on models that
support it) — the §8.3 realization of the `dimensions` passthrough that 017 (TEI) and 020 (Jina) assert
on their wires.

**Spec sections exercised:**

- retrieval-provider §2 — *Embedding runtime config* `dimensions` (optional, caller controls output
  vector size on providers that support it).
- retrieval-provider §4 — `dimensions` field on the response MUST equal the dimensionality of each
  inner vector (cross-check invariant).
- retrieval-provider §8.3 OpenAI-compatible embeddings — `/v1/embeddings`: `dimensions` →
  wire `dimensions` when set.

**Cases:**

1. `dimensions_maps_to_wire_dimensions_field` — `embed(config={dimensions: 4})`. The wire request MUST
   carry `dimensions: 4` alongside `{model, input}` (no `input_type` / `task` / `encoding_format`), with
   `Authorization: Bearer` present. Single input; the response is a one-element `data` array of a
   length-4 vector; `EmbeddingResponse.dimensions` MUST equal the inner vector length.

**What passes:**

- The wire request carries `dimensions: 4`; `model` and the `Authorization: Bearer` header are present.
- The response one-element `data` array maps to a single length-4 vector; the `dimensions` field
  matches the inner vector length; `usage.prompt_tokens` → `input_tokens`.

**What fails:**

- `dimensions` omitted from the wire request when supplied, or sent under a wrong key.
- The `dimensions` field on the response does not match the inner vector length.
