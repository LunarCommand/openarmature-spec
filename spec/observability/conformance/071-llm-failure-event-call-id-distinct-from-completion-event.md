# 071 — `LlmFailedEvent.call_id` distinct from `LlmCompletionEvent.call_id`

Verifies graph-engine §6's `LlmFailedEvent.call_id` field contract (per proposal 0058) —
each call gets its own freshly minted identifier, distinct from any sibling
`LlmCompletionEvent`'s `call_id` from a different call. The two event variants share the
same per-call slot semantics.

**Spec sections exercised:**

- graph-engine §6 — `LlmFailedEvent.call_id` field (proposal 0058).
- graph-engine §6 — `LlmCompletionEvent.call_id` field (proposal 0057).

**Cases:**

1. `call_id_distinct_across_success_and_failure_calls` — Graph chains two LLM-calling
   nodes; first succeeds (emits `LlmCompletionEvent`), second fails (emits `LlmFailedEvent`).
   Both events carry non-null `call_id` values; the two values are distinct.

**Per-suite directive (per conformance-adapter §3.2):**

- `event_counts: [{event_type, count}, ...]` — list form of the existing scalar
  `event_count` directive (per fixture 067) for fixtures asserting on multiple event-type
  counts in the same observer block. Adapters MUST verify each item in the list against
  the named event type's count in the observer's collected storage. Introduced here for
  the failure-event suite where most fixtures assert presence of one event-type AND
  absence of another (mutual-exclusion).

**What passes:**

- Exactly one `LlmCompletionEvent` and one `LlmFailedEvent` observed.
- Both events carry non-empty `call_id` strings.
- The two `call_id` values are pairwise distinct.

**What fails:**

- Either event has a null `call_id` (the always-present contract is broken).
- Both events carry the same `call_id` (the impl re-used an identifier — contract
  mandates fresh-mint per `provider.complete()` call).
- The success event's `call_id` is sourced from the response identifier (`response_id`)
  rather than minted by the impl — these are spec-distinct fields per proposal 0057.
