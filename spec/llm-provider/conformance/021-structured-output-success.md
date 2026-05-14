# 021 — Structured Output Success

`complete()` called with a `response_schema`; the provider returns valid
JSON matching the schema. Happy path: `Response.parsed` carries the
parsed-and-validated value, `Response.message.content` carries the raw
provider bytes verbatim, and `finish_reason` is `"stop"`.

**Spec sections exercised:**

- §5 `complete()` with `response_schema` parameter — the call constrains
  the model's output to conform to the schema.
- §6 `parsed` field — populated when the call supplied `response_schema`
  and the model returned structured content.
- §6 `message.content` preservation — carries the provider's content
  string verbatim (NOT re-serialized from `parsed`).
- §8.5 wire mapping — outbound request includes `response_format` with
  `json_schema` body.

**What passes:**

- Wire request includes `response_format.json_schema` with the supplied
  schema verbatim and `strict: true`.
- `Response.parsed == {name: "Alice", age: 30}`.
- `Response.message.content` is the literal `'{"name":"Alice","age":30}'`
  string.
- `finish_reason == "stop"`.

**What fails:**

- `response_format` absent from the wire — would mean `response_schema`
  wasn't applied.
- `Response.parsed` is absent or differs from the deserialized content —
  would mean the validation/parsing path isn't being exercised.
- `message.content` is re-serialized form of `parsed` (e.g., reformatted
  whitespace or sorted keys) — violates §6's verbatim-preservation rule.
