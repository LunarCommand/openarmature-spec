# 060 — `LlmCompletionEvent.input_messages` populated from call arguments

Verifies graph-engine §6's `LlmCompletionEvent.input_messages` field (per proposal 0057). The
typed event MUST carry the §3 message list of llm-provider the call was made with, in spec-
canonical `{role, content, tool_calls?, tool_call_id?}` shape.

**Spec sections exercised:**

- graph-engine §6 — `LlmCompletionEvent.input_messages` field (proposal 0057).
- llm-provider §3 — message shape.

**Cases:**

1. `input_messages_populated_from_call_arguments` — Graph with one LLM-calling node sending a
   two-message conversation (system + user). The typed event carries `input_messages` with
   both records in spec-canonical shape.

**What passes:**

- The typed event's `input_messages` is a 2-element list matching the call's message arguments.
- Each record carries `{role, content}` per llm-provider §3.

**What fails:**

- `input_messages` is null or missing when the call had non-empty message arguments.
- `input_messages` is the JSON-encoded string form §5.5.1 emits on the OTel span (the typed
  event field is native; the JSON-encoded form is for the span attribute).
- `input_messages` collapsed, reordered, or otherwise transformed relative to the call's
  arguments.
