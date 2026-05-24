# 005 — OpenAI Wire Mapping

Verifies the §8.1 OpenAI-compatible wire format mapping bidirectionally: spec inputs translate to
the expected OpenAI request body, and OpenAI response bodies translate back to the spec
`Response` shape. Provider-specific extensions (logprobs, vendor stats) round-trip via
`Response.raw` verbatim.

The fixture format is the table-style shape with an extra `expected_wire_request` field per
case. The harness MUST capture the implementation's outbound HTTP body and assert it equals
`expected_wire_request` (key-by-key; mapping key order is not significant).

**Spec sections exercised:**

- §8.1.1 Request mapping — message roles, tool_calls serialization, tools schema, runtime config.
- §8.1.2 Response mapping — message extraction, finish_reason translation including `function_call`
  legacy → `tool_calls`, usage extraction.
- §8.1.2 `raw` — provider-specific extensions surface verbatim.
- §6 RuntimeConfig — temperature, max_tokens, top_p, seed pass through unchanged.

**Cases:**

1. `simple_text_completion` — system + user messages, no tools, no config. Verifies basic message
   role mapping and the required `model` field.
2. `tool_call_with_serialized_arguments` — assistant `tool_calls` with mapping arguments.
   Verifies that arguments serialize to a JSON-encoded *string* on the wire (per OpenAI's
   schema) while the spec stores the deserialized mapping. Also verifies the §8.1.1 wrapping of
   tools as `{type: function, function: {...}}`.
3. `runtime_config_passthrough` — temperature, max_tokens, top_p, seed map directly to OpenAI's
   request body fields.
4. `function_call_legacy_finish_reason_mapping` — OpenAI's legacy `finish_reason:
   "function_call"` MUST map to the spec's `tool_calls`. The mock response also includes a
   provider-specific `logprobs` field; the implementation MUST preserve it in `Response.raw`
   verbatim per §6 / §8.1.2.

**What passes:**

- Each outbound HTTP request equals `expected_wire_request` (mapping key order ignored).
- For case 2, the wire body's `messages[1].tool_calls[0].function.arguments` is the JSON-encoded
  string `'{"expression":"2+2"}'`, NOT the mapping `{expression: "2+2"}`.
- For case 2, the spec-level `Response.message.tool_calls[0].arguments` (when applicable) is the
  parsed mapping.
- For case 4, `Response.finish_reason == "tool_calls"` (translated from `function_call`).
- For case 4, `Response.raw.choices[0].logprobs` carries the unredacted provider-supplied
  logprobs.

**What fails:**

- The implementation sends `arguments` as a mapping on the wire (OpenAI requires a string).
- `tools` are sent without the `{type: function, function: {...}}` wrapping.
- The implementation maps `function_call` to `error` or omits the translation.
- The implementation strips `logprobs` (or any other provider-specific field) from `raw`.
- RuntimeConfig fields are renamed or restructured on the wire.
