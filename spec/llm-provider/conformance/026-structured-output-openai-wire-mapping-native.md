# 026 — Structured Output Native OpenAI Wire Mapping

Verifies §8.1.5 wire mapping: when `response_schema` is supplied, the
outbound HTTP request body includes a `response_format` field carrying
`type: "json_schema"`, the user's schema verbatim under
`json_schema.schema`, and `strict: true`. The provider is configured
as natively supporting `response_format` so the implementation takes
the native path (not the §8.1.5.1 fallback).

**Spec sections exercised:**

- §8.1.5 Structured output wire mapping — request body shape with
  `response_format.json_schema.{name, schema, strict}`.
- §8.1.5 `strict: true` is set when the supplied schema satisfies
  strict-mode constraints (this test's schema does:
  `additionalProperties: false`, all properties in `required`).
- §8.1.5 the supplied schema is passed verbatim under
  `json_schema.schema`.

**What passes:**

- Outbound wire `response_format.type == "json_schema"`.
- `response_format.json_schema.schema` is exactly the user's schema.
- `response_format.json_schema.strict == true`.
- `Response.parsed == {value: 42}` (round-trips from the mock response).

**What fails:**

- `response_format` absent from the wire.
- `strict` is `false` when the schema satisfies strict-mode constraints.
- `json_schema.schema` is transformed (e.g., normalized, re-keyed) —
  the spec mandates verbatim pass-through.
