# 070 — `LlmFailedEvent` dispatch on `provider_invalid_request`

Verifies graph-engine §6's `LlmFailedEvent` dispatch contract for a different llm-provider §7
category — `provider_invalid_request`, raised at the implementation's `complete()` boundary
by the cross-message `tool_call_id` matching check, before any wire contact occurs.

**Spec sections exercised:**

- graph-engine §6 — `LlmFailedEvent` typed event variant (proposal 0058).
- llm-provider §3 — message-shape constraints (a `tool` message's `tool_call_id` MUST match an
  earlier assistant `ToolCall`; the cross-message matching check is at the `complete()` boundary).
- llm-provider §7 — `provider_invalid_request` error category.

**Cases:**

1. `llm_failure_event_dispatched_on_provider_invalid_request` — Node sends a tool-role
   message whose `tool_call_id` is present but matches no earlier assistant `ToolCall`. The
   `complete()`-boundary matching check raises `provider_invalid_request` before contacting
   the provider. The typed event carries `error_category = "provider_invalid_request"`.
   Companion to fixture 069 — verifies the typed-event dispatch contract is consistent across
   §7 categories.

**What passes:**

- `LlmFailedEvent` observed with `error_category = "provider_invalid_request"`.
- Mutual exclusion holds (zero `LlmCompletionEvent`).
- Exception propagates as `provider_invalid_request`.

**What fails:**

- `error_category` set to a different value (e.g., a generic `validation_error`); the spec
  mandates one of the §7 enumeration.
- The boundary matching check does NOT raise (the impl proceeds to the wire with the
  unmatched `tool_call_id`, where the provider raises a different error) — the spec mandates
  the `complete()`-boundary validation rule per llm-provider §3.
