# 009 — Duplicate index surfaces `provider_invalid_response`

Verifies retrieval-provider §6's unique-index cross-impl invariant. A `RerankProvider` receiving two
results with the same `index` MUST raise `provider_invalid_response` — a duplicate index breaks the
one-result-per-input-document contract the `index` field encodes.

**Spec sections exercised:**

- retrieval-provider §6 — unique-index invariant (the same `index` MUST NOT appear twice in
  `results`).
- retrieval-provider §7 — `provider_invalid_response` error category.

**Cases:**

1. `rerank_duplicate_index_raises_provider_invalid_response` — 3 input documents; mocked response
   returns two results both with `index=0`. The adapter MUST detect the duplicate and raise
   `provider_invalid_response`.

**What passes:**

- `provider_invalid_response` raised, attributed to the calling node.

**What fails:**

- The adapter returns the duplicate-index response without detection.
- A different §7 category is raised.
