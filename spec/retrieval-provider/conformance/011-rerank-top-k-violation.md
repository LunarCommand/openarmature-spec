# 011 — `top_k` violation surfaces `provider_invalid_response`

Verifies retrieval-provider §6's `len(results) <= top_k` cross-impl invariant. A `RerankProvider`
whose provider returns **more** results than the caller-supplied `top_k` MUST raise
`provider_invalid_response`. Negative-control counterpart to the pass-through cases in fixture 010.

**Spec sections exercised:**

- retrieval-provider §6 — `len(results) <= top_k` invariant; implementations MUST raise
  `provider_invalid_response` when the provider returns more results than requested.
- retrieval-provider §7 — `provider_invalid_response` error category.

**Cases:**

1. `rerank_top_k_violation_raises_provider_invalid_response` — `top_k=2` over 3 documents; mocked
   response returns 3 results. The adapter MUST detect the violation and raise
   `provider_invalid_response`.

**What passes:**

- `provider_invalid_response` raised, attributed to the calling node.

**What fails:**

- The adapter silently returns all 3 results (or truncates to 2) instead of raising — the invariant
  is not enforced.
- A different §7 category is raised.
