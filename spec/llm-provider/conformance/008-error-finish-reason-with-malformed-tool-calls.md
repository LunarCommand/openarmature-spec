# 008 — Error finish_reason with malformed tool_calls

Verifies the §3 "Validation under `finish_reason: \"error\"`" rule: when a degraded response
arrives, all tool calls flow through to `Response.message.tool_calls` regardless of validity,
the implementation does NOT raise, and `Response.raw` carries the original bytes verbatim so
applications can repair-and-continue.

This is the load-bearing test for the spec's deliberate transparency choice: malformed data is
surfaced rather than dropped, enabling user-side repair utilities (e.g., partial-JSON fixers).

**Spec sections exercised:**

- §3 ToolCall record — `arguments` may be `null` under `finish_reason: "error"` (unparseable
  bytes) or a parsed mapping that does not conform to the schema.
- §3 "Validation under `finish_reason: \"error\"`" — implementation MUST NOT raise
  `provider_invalid_response`; tool calls flow through with whatever can be parsed.
- §6 `finish_reason: "error"` — degraded but parseable response.
- §6 `Response.raw` — verbatim original, including the truncated arguments string.

**The fixture's three tool calls:**

1. **`call_valid_001`** — `arguments: '{"city": "Boston"}'` parses to `{city: "Boston"}` and
   conforms to the schema.
2. **`call_schema_violating_002`** — `arguments: '{"city": "Seattle", "extra": "ignored"}'`
   parses to a mapping, but `additionalProperties: false` forbids `extra`. Under any other
   finish_reason this would have raised `provider_invalid_response`; under `error` it flows
   through as a mapping.
3. **`call_truncated_003`** — `arguments: '{"city": "London", "ext'` (truncated). The
   implementation cannot parse this as JSON, so `arguments` populates as `null`. The original
   string is available via `Response.raw.choices[0].message.tool_calls[2].function.arguments`
   for application repair code.

**What passes:**

- `complete()` returns successfully (no exception raised).
- `Response.finish_reason == "error"`.
- `Response.message.tool_calls` has exactly three entries in order.
- `tool_calls[0].arguments == {city: "Boston"}`.
- `tool_calls[1].arguments == {city: "Seattle", extra: "ignored"}`.
- `tool_calls[2].arguments` is `null`.
- The original truncated arguments string is present in `Response.raw`.

**What fails:**

- The implementation raises `provider_invalid_response` because of the truncated entry.
- The implementation drops the malformed entries from `Response.message.tool_calls` (loses
  information; user repair utilities can't act).
- The implementation populates `arguments` for the truncated entry with an empty mapping `{}`
  instead of `null` (would silently mislead users into thinking the call had no args).
- The schema-violating entry is rejected (forces users to choose between strict validation and
  any error tolerance).
