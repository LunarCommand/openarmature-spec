# 067 — `LlmCompletionEvent.call_id` always present and distinct per call

Verifies graph-engine §6's `LlmCompletionEvent.call_id` field (per proposal 0057). Always
present (never null); freshly minted per `provider.complete()` call; unique within the
implementation's run.

**Spec sections exercised:**

- graph-engine §6 — `LlmCompletionEvent.call_id` field (proposal 0057).

**Cases:**

1. `call_id_always_present_and_distinct_across_three_calls` — Graph chains three LLM-calling
   nodes in sequence. The collector observer collects three `LlmCompletionEvent`s. Each
   event's `call_id` is a non-null string AND the three values are distinct.

**Per-directory directives (per conformance-adapter §3.2):**

- `expected.observers.<name>.event_count: {event_type: <T>, count: <int>}` — the adapter
  MUST assert exactly `count` events of the given type are present in the observer's
  collected storage.
- Invariant `call_ids_pairwise_distinct` — the adapter MUST iterate the observer's collected
  `LlmCompletionEvent` records and verify all `call_id` values are pairwise distinct.
- Invariant `all_call_ids_are_non_empty_strings` — every collected `LlmCompletionEvent`
  carries a non-null, non-empty-string `call_id`.

**What passes:**

- All three `LlmCompletionEvent` records have non-null `call_id` values.
- The three `call_id` values are pairwise distinct.
- Each `call_id` is a non-empty string (the wire shape is unconstrained — UUID, ULID,
  monotonic counter all fine — but the value MUST be a string).

**What fails:**

- Any `call_id` is null or absent.
- Two or more `call_id` values collide (the impl minted the same identifier for distinct
  calls).
- `call_id` is sourced from the provider response (e.g., derived from `response_id`) rather
  than minted by the implementation. The spec carves these as distinct surfaces — `call_id`
  is the implementation's own token, freshly minted per call; `response_id` is the
  provider-returned identifier.
