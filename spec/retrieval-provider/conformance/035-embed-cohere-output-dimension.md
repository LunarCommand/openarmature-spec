# 035 — Cohere `/v2/embed` `output_dimension` passthrough (Matryoshka)

Verifies that `EmbeddingRuntimeConfig.dimensions` maps onto Cohere's **`output_dimension`** wire field
(§8.4 *`output_dimension` / `embedding_types` / `truncate`*) — the Cohere realization of the `dimensions`
passthrough that 017 (TEI), 020 (Jina), and 024 (OpenAI) assert on their wires. Cohere names the same
Matryoshka knob `output_dimension`, so the source field is OA's declared `dimensions`, not the extras bag.

**Spec sections exercised:**

- retrieval-provider §2 — *Embedding runtime config* `dimensions` (absent-is-meaningful).
- retrieval-provider §4 — the `dimensions` cross-check invariant (`EmbeddingResponse.dimensions` equals the
  inner-vector length).
- retrieval-provider §8.4 Cohere — `EmbeddingRuntimeConfig.dimensions` → Cohere's `output_dimension` when
  set; omitted otherwise (Cohere's model default applies).

**Cases:**

1. `dimensions_maps_to_output_dimension_field` — `embed(config={dimensions: 8})` ⇒ the wire request carries
   `output_dimension: 8` alongside `{model, input_type: "search_document", texts, embedding_types:
   ["float"], truncate: "NONE"}`. The response carries one 8-d vector under `embeddings.float`;
   `EmbeddingResponse.dimensions` equals the inner-vector length.
2. `no_dimensions_omits_output_dimension` — `embed()` with no `dimensions`. The wire request MUST omit
   `output_dimension` (the body is exactly `{model, input_type: "search_document", texts, embedding_types:
   ["float"], truncate: "NONE"}`); the response carries one 4-d vector (the model default).

**Dimension value note:** `8` (rather than one of Cohere's documented `256` / `512` / … values) is used so
the mocked response vector length matches the requested `output_dimension` and stays within the corpus's
tiny-vector convention; the wire-mapping assertion (`dimensions` → `output_dimension`) is identical
regardless of the numeric value.

**What passes:**

- `dimensions: 8` produces `output_dimension: 8` on the wire; an absent `dimensions` omits the field.
- `embedding_types: ["float"]` and `truncate: "NONE"` present on both; the `Authorization: Bearer`
  header present.
- `EmbeddingResponse.dimensions` equals the inner-vector length on both cases.

**What fails:**

- `dimensions` routed through the extras bag instead of the declared `output_dimension` field.
- `output_dimension` emitted when no `dimensions` was supplied, or omitted when one was.
- The `dimensions` field disagrees with the inner-vector length.
