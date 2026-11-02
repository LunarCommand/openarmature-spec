# 041 — Anthropic structured-output fallback

Verifies the §8.2.5.1 fallback for models without native `output_config.format` support: tool-call
coercion where the adapter declares it, and otherwise prompt augmentation.

**Spec sections exercised:**

- §8.2.5.1 — when native structured output is unavailable and the caller supplies no tools,
  construct a synthetic tool whose `input_schema` is the `response_schema`, add it to `tools`,
  and set `tool_choice` to `{type: "tool", name: <synthetic name>}`. The response's
  `tool_use.input` for the synthetic tool becomes `Response.parsed`.
- §8.2.5.1 prompt augmentation: the request is sent otherwise unmodified, apart from a schema
  directive, the text response is parsed and validated, and the caller's original `messages` MUST
  be left unchanged.

**Gates:** §8.2.5.1 says an implementation SHOULD prefer tool-call coercion, so the first case is
gated on `anthropic_fallback_tool_coercion`. Falling back at all is not a SHOULD, so the second case,
gated on the capability's `false` value, checks what holds without coercion: no `output_config`, no
synthetic tool, a parsed text answer and unchanged caller messages. That path is prompt augmentation,
which may put its directive in the system field or the messages, so the second case asserts neither.
Every adapter runs one of the two cases.

**Harness note:** the synthetic tool's `name` is implementation-derived. The
`<tool_name_synthetic>` binding token matches it in `tools` and in `tool_choice.name`, so the two
must hold the same value. The tool's `description` is not asserted, since §8.2.5.1 does not
require one. The mock's `tool_use` block names the synthetic tool through
`<request_tool_choice_name>`, which the harness replaces with the `tool_choice` name the request
carried. The harness note in fixture 001's header defines the capability, the token and the echo.

**What passes:**

- Case 1: a synthetic tool carrying the `response_schema` under `input_schema`, exactly, is the only
  entry in `tools`; `tool_choice` forces that tool by the same name; the request carries no
  `output_config`; and the response's `tool_use.input` `{value: 42}` becomes `Response.parsed`.
- Case 2: the request carries no `output_config`, `tools` or `tool_choice`, the text answer
  `{"value":42}` becomes `Response.parsed`, and the caller's messages are left unchanged
  (`caller_messages_unmodified`).

**What fails:**

- No synthetic tool added, on an adapter that declares coercion.
- `tool_choice.name` differs from the synthetic tool's `name`.
- `output_config` sent although the model lacks native structured output, on either path.
- `Response.parsed` not extracted from `tool_use.input`.
- The caller's messages modified in place on the prompt-augmentation path.
