# 002 — Tool Call Roundtrip

Verifies the user → assistant-tool-call → tool-result → assistant-text flow that an agent loop
performs once per tool the model invokes. Also verifies that tool-call ids are preserved verbatim
across the round-trip — the load-bearing property for §3's "Cross-provider id round-tripping"
rule.

The fixture format is documented in fixture 001's `.md`.

**Spec sections exercised:**

- §3 Message shape — `assistant` with `tool_calls` (and empty `content`); `tool` with
  `tool_call_id` matching the earlier `assistant` `ToolCall.id`.
- §3 ToolCall record — `id`, `name`, `arguments` populated; arguments parsed as a mapping.
- §3 "Cross-provider id round-tripping" — the implementation MUST preserve the provider-supplied
  id verbatim through the second `complete()`. The id used here (`call_abc123_with_underscores`)
  is non-trivial to expose any normalization the implementation might attempt.
- §4 Tool definition — `parameters` as a JSON Schema object (type, properties, required).
- §6 `finish_reason: "tool_calls"` — provider returned tool calls, awaiting results.
- §8.1 OpenAI request mapping — `assistant` `tool_calls` and `tool` `tool_call_id` map to the
  OpenAI wire format with the verbatim id.

**What passes:**

- First `complete()` returns `Response.message.tool_calls` containing one entry with the canned id
  and `arguments == {city: "Boston"}` parsed as a mapping.
- `Response.finish_reason == "tool_calls"`.
- Second `complete()` accepts the message list with the matching `tool_call_id` and returns the
  final assistant text.
- The tool-call id `call_abc123_with_underscores` flows through unchanged: same string in the
  first response's `tool_calls[0].id`, same string in the second call's `tool_call_id`, same
  string in the wire format the implementation sends.

**What fails:**

- The implementation rewrites the id (e.g., regenerates as `openarmature_<uuid>`).
- The implementation strips trailing/leading characters or normalizes the id format.
- `arguments` is left as a JSON-encoded string instead of being parsed to a mapping.
- The `finish_reason` is reported as `"stop"` despite tool calls being present.
- The tool message is rejected because the implementation expects a different id format.
