# 070 — `LlmFailedEvent` dispatch on `provider_invalid_request`

Verifies graph-engine §6's `LlmFailedEvent` dispatch contract for a different llm-provider §7
category — `provider_invalid_request`, raised by the implementation's pre-send validation
layer before any wire contact occurs.

**Spec sections exercised:**

- graph-engine §6 — `LlmFailedEvent` typed event variant (proposal 0058).
- llm-provider §3 — message-shape constraints (tool-role messages MUST carry `tool_call_id`).
- llm-provider §7 — `provider_invalid_request` error category.

**Cases:**

1. `llm_failure_event_dispatched_on_provider_invalid_request` — Node sends a malformed
   tool-role message without `tool_call_id`. The impl's pre-send validation raises
   `provider_invalid_request` before contacting the provider. The typed event carries
   `error_category = "provider_invalid_request"`. Companion to fixture 069 — verifies the
   typed-event dispatch contract is consistent across §7 categories.

**What passes:**

- `LlmFailedEvent` observed with `error_category = "provider_invalid_request"`.
- Mutual exclusion holds (zero `LlmCompletionEvent`).
- Exception propagates as `provider_invalid_request`.

**What fails:**

- `error_category` set to a different value (e.g., a generic `validation_error`); the spec
  mandates one of the §7 enumeration.
- Pre-send validation does NOT raise (the impl swallows the malformed message and proceeds
  to the wire, where the provider raises a different error) — the spec mandates the
  pre-send validation rule per llm-provider §3.
