# 077 — `EmbeddingEvent.call_id` always-present and distinct per call

Verifies graph-engine §6's per-call `call_id` mint contract for `EmbeddingEvent` (per proposal
0059). Each `embed()` call mints its own `call_id`; the field is always non-null. Mirrors
fixture 067 for the LLM-side variant.

**Spec sections exercised:**

- graph-engine §6 — `EmbeddingEvent.call_id` per-call mint rule.

**Cases:**

1. `multiple_embed_calls_have_distinct_call_ids` — Two embedding-calling nodes in series.
   Asserts two `EmbeddingEvent` events observed; their `call_id` fields are non-null and
   distinct.

**What passes:**

- Two events observed with non-null, distinct `call_id` values.

**What fails:**

- The two `call_id` values match — the adapter reused a call identifier across calls.
- Either `call_id` is null — the adapter did not mint the per-call identifier.
