# 008 — Out-of-range index surfaces `provider_invalid_response`

Verifies retrieval-provider §6's valid-index cross-impl invariant. A `RerankProvider` receiving a
result whose `index` falls outside `[0, len(documents))` MUST raise `provider_invalid_response` —
an out-of-range index would break the caller-side `documents[result.index]` lookup the `index` field
is load-bearing for.

**Spec sections exercised:**

- retrieval-provider §6 — valid-index invariant (each result's `index` MUST satisfy
  `0 <= index < len(documents)`).
- retrieval-provider §7 — `provider_invalid_response` error category.

**Cases:**

1. `rerank_out_of_range_index_raises_provider_invalid_response` — 2 input documents; mocked response
   returns a result with `index=5`. The adapter MUST detect the out-of-range index and raise
   `provider_invalid_response`.

**What passes:**

- `provider_invalid_response` raised, attributed to the calling node.

**What fails:**

- The adapter returns the malformed response to the caller without detection — the cross-impl
  invariant is not enforced.
- A different §7 category is raised — the classifier did not recognize the index violation.
