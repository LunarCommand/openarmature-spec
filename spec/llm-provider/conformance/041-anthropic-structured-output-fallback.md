# 041 — Anthropic structured-output fallback (tool-call coercion)

Verifies the §8.2.5.1 tool-call-coercion fallback for models without native
`output_config.format` support.

**Spec sections exercised:**

- §8.2.5.1 — when native structured output is unavailable and the caller supplies no tools,
  construct a synthetic tool whose `input_schema` is the `response_schema`, add it to `tools`,
  and set `tool_choice` to `{type: "tool", name: <synthetic name>}`. The response's
  `tool_use.input` for the synthetic tool becomes `Response.parsed`.

**Harness note:** the synthetic tool's `name` and `description` are implementation-derived; the
literal `"*"` is the harness wildcard (present, non-empty string, value exempt from literal
comparison). The `tool_choice.name` MUST equal the synthetic tool's `name` — a relationship the
MD documents and the YAML approximates with matched wildcards.

**What passes:**

- A synthetic tool carrying the `response_schema` under `input_schema` appears in `tools`.
- `tool_choice` forces that tool.
- The response's `tool_use.input` `{value: 42}` becomes `Response.parsed`.

**What fails:**

- No synthetic tool added (the model has no native path, so coercion is required).
- `Response.parsed` not extracted from `tool_use.input`.
