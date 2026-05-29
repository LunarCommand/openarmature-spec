# 040 — Anthropic native structured output

Verifies the §8.2.5 native structured-output path.

**Spec sections exercised:**

- §8.2.5 — `response_schema` maps to `output_config.format = {type: "json_schema", schema}` with
  the schema verbatim under `schema`; the GA path requires no beta header.
- §8.2.5 — the response's text content is parsed into `Response.parsed` and validated against
  `response_schema` per §6.

**What passes:**

- The wire request carries `output_config.format` with `type: "json_schema"` and the supplied
  schema under `schema`.
- The response text `{"value":42}` is parsed into `Response.parsed = {value: 42}`.

**What fails:**

- Structured output emitted via tool-call coercion (the legacy fallback) when native
  `output_config.format` is available.
- `output_config.format` absent or the schema not passed verbatim under `schema`.
- `Response.parsed` not populated from the response text.
