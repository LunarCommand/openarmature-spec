# 102 — `RerankEvent.call_id` distinct across calls

Verifies graph-engine §6's per-call `call_id` contract for `RerankEvent`. Multiple `rerank()` calls
in the same invocation emit events with distinct, non-null `call_id` values.

**Spec sections exercised:**

- graph-engine §6 — `RerankEvent.call_id` is a per-call disambiguator, always present, freshly
  minted per `rerank()` call.

**Cases:**

1. `multiple_rerank_calls_have_distinct_call_ids` — two rerank nodes in series; both succeed. Two
   `RerankEvent`s observed with distinct, non-null `call_id` values.

**What passes:**

- Two `RerankEvent`s, each with a distinct non-null `call_id`.

**What fails:**

- The two events share a `call_id` — the disambiguator is not per-call.
- A `call_id` is null.
