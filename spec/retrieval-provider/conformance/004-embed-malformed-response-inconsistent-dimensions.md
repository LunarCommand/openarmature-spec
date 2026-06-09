# 004 — Inconsistent dimensions surfaces `provider_invalid_response`

Verifies retrieval-provider §4's dimensionality-consistency cross-impl invariant. An
`EmbeddingProvider` receiving a response whose inner vectors have inconsistent lengths MUST raise
`provider_invalid_response` per §5.

**Spec sections exercised:**

- retrieval-provider §4 — dimensionality consistency invariant (all vectors in a single response
  MUST share the same dimensionality).
- retrieval-provider §5 — `provider_invalid_response` error category.

**Cases:**

1. `embed_raises_provider_invalid_response_on_inconsistent_dimensions` — Provider called with
   3 input strings; mocked response returns 3 vectors with inner-list lengths 4, 4, and 3. The
   adapter MUST detect the dimensionality mismatch and raise `provider_invalid_response`.

**What passes:**

- `provider_invalid_response` raised, attributed to the calling node.

**What fails:**

- The adapter returns the malformed response to the caller without detection.
- A different §7 category is raised.
