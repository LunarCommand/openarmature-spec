# 010 — `top_k` contract pass-through

Verifies the three permitted `top_k` outcomes from retrieval-provider §5 / §6: an exact match,
a provider undershoot (fewer results than requested), and `top_k` exceeding the document count.
All three pass through unchanged. The negative control — a provider returning **more** than `top_k` —
is split out into fixture 011 so this fixture stays a pass-through assertion.

**Spec sections exercised:**

- retrieval-provider §5 — `top_k` parameter semantics (`None` means all; provider returns at most
  `len(documents)`; MAY return fewer).
- retrieval-provider §6 — `len(results) <= top_k` when `top_k` is supplied; results MAY be shorter.

**Cases:**

1. `top_k_exact` — `top_k=2` over 3 documents; provider returns 2 results. Result count equals
   `top_k`.
2. `top_k_undershot` — `top_k=3`; provider returns 2 results (relevance filtering). Permitted.
3. `top_k_larger_than_documents` — `top_k=10` over 3 documents; provider returns 3 results. `top_k`
   exceeding `len(documents)` is permitted.

**What passes:**

- Each case returns the provider's results unchanged with `len(results) <= top_k`.

**What fails:**

- The adapter pads or truncates the result set to force `len(results) == top_k`.
- An error is raised for the permitted undershoot or `top_k > len(documents)` cases.
