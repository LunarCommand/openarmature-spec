# 025 — Structured Output With Tool Calls

`complete()` called with both `tools` and `response_schema`; the model
returns `tool_calls` instead of structured content. Verifies the
tool-call-path-vs-structured-path mutual exclusion per §5/§6 — the
model's choice is signaled by `finish_reason`, and the structured-path
fields (`parsed`) MUST be absent on the tool-call path.

**Spec sections exercised:**

- §5 — when `tools` and `response_schema` are both supplied, the model
  decides which path; `finish_reason` signals the choice.
- §6 — `parsed` is absent when `finish_reason` is `"tool_calls"`,
  regardless of whether `response_schema` was supplied.
- §6 — the tool-call path and structured-content path are mutually
  exclusive at the response level.

**What passes:**

- `finish_reason == "tool_calls"`.
- `Response.message.tool_calls` is populated with the model's tool call.
- `Response.parsed` is absent (null/None/undefined).

**What fails:**

- `parsed` is populated despite the tool-call finish_reason — would
  violate §6's mutual-exclusion rule.
- `complete()` raises `structured_output_invalid` because the tool-call
  content didn't validate as the schema's object shape — would mean the
  implementation tried to validate the tool-call message body against
  the schema, which is wrong.
