# 003 — Mismatched vector count surfaces `provider_invalid_response`

Verifies retrieval-provider §4's vector-count cross-impl invariant. An `EmbeddingProvider`
receiving a response with fewer vectors than input strings MUST raise
`provider_invalid_response` per §7.

**Spec sections exercised:**

- retrieval-provider §4 — vector-count invariant (length of `vectors` MUST equal length of `input`).
- retrieval-provider §7 — `provider_invalid_response` error category.

**Cases:**

1. `embed_returns_provider_invalid_response_on_vector_count_mismatch` — Provider called with
   3 input strings; mocked response returns only 2 vectors. The adapter MUST detect the
   mismatch and raise `provider_invalid_response`.

**What passes:**

- `provider_invalid_response` raised, attributed to the calling node.

**What fails:**

- The adapter returns the malformed response to the caller without detection — the cross-impl
  invariant is not enforced.
- A different §7 category is raised (e.g., `provider_invalid_request`) — the classifier did not
  recognize the response-shape violation.
