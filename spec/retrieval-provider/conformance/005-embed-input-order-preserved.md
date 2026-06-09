# 005 — Input order preserved in embedding response

Verifies retrieval-provider §3's input-order-preservation contract. The vector at output index
`i` MUST correspond to the embedding of `input[i]`. Implementations MUST NOT permute vector
position relative to input position.

**Spec sections exercised:**

- retrieval-provider §3 — `embed()` input-order preservation rule (MUST NOT permute).

**Cases:**

1. `embed_preserves_input_order_in_response` — Provider called with 3 input strings. Mocked
   response returns identifiable vectors (the first dimension encodes the expected input index).
   Asserts the response carries `vectors[0]` with first dim 1.0, `vectors[1]` with first dim 2.0,
   `vectors[2]` with first dim 3.0.

**What passes:**

- Vector positions in the response match input positions.

**What fails:**

- The adapter sorts, deduplicates, or otherwise permutes vectors — the input-order contract is
  broken.
