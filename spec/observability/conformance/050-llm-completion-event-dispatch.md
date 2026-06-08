# 050 — Typed `LlmCompletionEvent` dispatch on LLM completion

Verifies graph-engine §6's *Typed LLM completion event* + observability §5.5.7. On every LLM
call that produces a structured response (per llm-provider §6), implementations MUST emit an
`LlmCompletionEvent` on the observer delivery queue. The event carries the typed field set
populated from the provider's response.

**Spec sections exercised:**

- graph-engine §6 — `LlmCompletionEvent` typed event variant; field set; dispatch contract.
- observability §5.5.7 — Typed event is the structured form of the §5.5 attribute surface.

**Cases:**

1. `llm_completion_event_dispatched_with_populated_fields` — A graph with one LLM-calling node;
   a mocked provider returns a structured response with known `usage`, `finish_reason`, and a
   `response_id`. A custom observer collects all events received. Asserts the observer received
   an `LlmCompletionEvent` whose typed fields match the response: `provider` is the configured
   provider id, `model` is the bound model, `usage.prompt_tokens` / `usage.completion_tokens` /
   `usage.total_tokens` match the mocked response, `finish_reason = "stop"`, `response_id` is
   the mocked id, and the identity / scoping fields (`invocation_id`, `node_name`, `namespace`,
   `attempt_index`) are populated correctly.

**Harness extensions:** the harness MUST support attaching a custom observer that retains
captured events in observer-internal storage (observers MUST NOT mutate state per graph-engine
§6), plus observer-introspection expectations that match a typed event present in that storage
by event type + field values.

**What passes:**

- Exactly one `LlmCompletionEvent` is observed for the single LLM call.
- The event's typed fields match the provider response.
- The event's identity / scoping fields (`invocation_id`, `node_name`, `namespace`,
  `attempt_index`, `fan_out_index`, `branch_name`) are populated per the calling node's
  position in the graph.
- `caller_invocation_metadata` is null (default; opt-in not enabled — see fixture 052).

**What fails:**

- No `LlmCompletionEvent` observed — the framework did not emit the typed event.
- The event's `usage` / `finish_reason` / `response_id` do not match the provider response.
- The event's `namespace` / `node_name` do not identify the calling node correctly.
- `LlmCompletionEvent` was emitted for a `provider_unavailable` exception path (failure case
  — see fixture 053).
