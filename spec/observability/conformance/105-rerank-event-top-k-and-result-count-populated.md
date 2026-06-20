# 105 — `RerankEvent.top_k`, `document_count`, `result_count` populated

Verifies graph-engine §6's contract for the rerank cardinality fields. `top_k` mirrors the
caller-supplied value (or null when the caller passed `None`); `document_count` mirrors the input
length; `result_count` mirrors the provider response.

**Spec sections exercised:**

- graph-engine §6 — `RerankEvent.top_k` (caller value or null), `document_count` (`len(documents)`),
  `result_count` (`len(response.results)`).

**Cases:**

1. `top_k_and_counts_populated_when_top_k_supplied` — `top_k=2` over 3 documents, 2 results. Event
   carries `top_k=2`, `document_count=3`, `result_count=2`.
2. `top_k_null_when_caller_passed_none` — no `top_k` over 3 documents, 3 results. Event carries
   `top_k=null`, `document_count=3`, `result_count=3`.

**What passes:**

- `top_k` reflects the caller's value (null when `None`); the counts match input and response.

**What fails:**

- `top_k` defaulted to a number when the caller passed `None`.
- `result_count` or `document_count` mismatched against the response / input.
