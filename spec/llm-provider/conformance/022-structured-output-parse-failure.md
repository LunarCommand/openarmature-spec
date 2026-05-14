# 022 — Structured Output JSON Parse Failure

`complete()` called with a `response_schema`; provider returns content
that is not valid JSON (truncated body). MUST raise
`structured_output_invalid`. Verifies the parse-failure half of §7's
`structured_output_invalid` semantics.

**Spec sections exercised:**

- §7 `structured_output_invalid` — raised when the provider's content
  cannot be parsed as JSON.
- §7 error payload — MUST expose the requested schema, the raw response
  content, and a failure description.

**What passes:**

- `complete()` raises `structured_output_invalid`.
- The error payload carries the requested `response_schema`, the raw
  response bytes (`'{"name":"Alice","age":'`), and a parse-failure
  description.

**What fails:**

- A different error category is raised (e.g.,
  `provider_invalid_response` — but that's wire-shape malformation, not
  schema-content failure).
- The error payload is missing the schema, raw content, or description.
- The call returns normally with `parsed` absent — would mean the
  validation step was skipped.
