# 017 — TEI `/embed` wire round-trip

Verifies the retrieval-provider §8.1 TEI embedding mapping on the `/embed` request and response wire
surfaces (the `input_type` path is fixture 013). The request always sends the array form
`{"inputs": [str]}`; `dimensions` maps to TEI's `dimensions` field when set; the TEI vector-array
response maps onto `EmbeddingResponse.vectors` in input order with §4's cross-impl invariants.

**Spec sections exercised:**

- retrieval-provider §8.1 TEI — `/embed`: `POST {base_url}/embed` with `{"inputs": [str]}` (always
  the array form per §3's "always a list"); `dimensions` maps to TEI's `dimensions` field; the
  response is the vector array in input order.
- retrieval-provider §3 / §4 — `embed()` preserves input order; `EmbeddingResponse` cross-impl
  invariants (vector count == input count, all inner vectors same dimensionality, `dimensions` field
  == inner length); `response_id` null when the provider returns none.

**Cases:**

1. `embed_array_form_response_in_input_order` — 3 inputs, no config. The wire request MUST be exactly
   `{"inputs": [s0, s1, s2]}` (array form, no `prompt_name`, no `dimensions`). The TEI vector-array
   response of dimension 4 MUST map to `vectors` in input order (distinct first components make the
   order check load-bearing), with `vectors` length 3, all inner length 4, `dimensions` 4,
   `response_id` null.
2. `embed_dimensions_maps_to_tei_dimensions_field` — `config={dimensions: 4}` ⇒ the wire request
   carries TEI's `dimensions` field alongside `inputs`; the one-element vector-array response holds.

**What passes:**

- The request is the array form even for a single-string caller; `dimensions` appears on the wire
  only when supplied; `prompt_name` is absent.
- Vectors map in input order; the cross-impl invariants hold; `response_id` is null.

**What fails:**

- The request sends a bare string instead of the array form, or emits `dimensions` / `prompt_name`
  when not supplied.
- Vectors permuted relative to input order, a mismatched vector count, inconsistent inner
  dimensionality, or a `dimensions` field disagreeing with the inner length.
- `response_id` fabricated when TEI returns none.
