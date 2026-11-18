# 091: A Streamed Gemini Function Call

Verifies llm-provider §8.3.6 (proposal 0128) for a streamed `functionCall` part. On the Gemini API a call
arrives whole in one chunk, so the mapping takes it as one complete call. It maps to a `ToolCall` by §8.3.2,
emits no token event, and sets `finish_reason` to `"tool_calls"`.

**Spec sections exercised:**

- llm-provider §8.3.6 *Assembly*: each `functionCall` part is one complete call.
- llm-provider §8.3.6 *Token events*: a `functionCall` part emits none.
- llm-provider §8.3.2: `tool_calls` from `functionCall` parts, and `"tool_calls"` when one is present.

**What passes:**

- `token_events` is empty.
- `message.tool_calls` holds the one call with its `id`, `name` and parsed `arguments`, and no signature.
- `finish_reason` is `"tool_calls"`, though Gemini reported `STOP`.
- Usage is 30, 8 and 38.

**What fails:**

- A token event for the call.
- `finish_reason` `"stop"`.
- The call dropped, or its arguments left as a string.

**Limits.** §3 lets an assistant message with tool calls have empty content and does not fix the form, so the
fixture does not assert `message.content`.
