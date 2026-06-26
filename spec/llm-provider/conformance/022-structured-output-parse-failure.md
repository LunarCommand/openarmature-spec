# 022 — Structured Output JSON Parse Failure

`complete()` called with a `response_schema`; provider returns content
that is not valid JSON — the model finishes normally (`finish_reason`
`"stop"`) but emits malformed JSON, not a max-tokens truncation (which
carries `finish_reason: "length"`; see observability fixture 120). MUST raise
`structured_output_invalid`. Verifies the parse-failure half of §7's
`structured_output_invalid` semantics.

**Spec sections exercised:**

- §7 `structured_output_invalid` — raised when the provider's content
  cannot be parsed as JSON.
- §7 error payload — MUST expose the requested schema, the raw response
  content, a failure description, and (per proposal 0082) the response's
  normalized `finish_reason` and token `usage`, sourced from the received
  (but unparseable) response.

**What passes:**

- `complete()` raises `structured_output_invalid`.
- The error payload carries the requested `response_schema`, the raw
  response bytes (`'{"name": "Alice" "age": 30}'`), and a parse-failure
  description.
- The error also carries the response's `finish_reason` (`"stop"`) and
  `usage` (the body's literal token counts), per proposal 0082.

**What fails:**

- A different error category is raised (e.g.,
  `provider_invalid_response` — but that's wire-shape malformation, not
  schema-content failure).
- The error payload is missing the schema, raw content, description,
  `finish_reason`, or `usage`.
- The call returns normally with `parsed` absent — would mean the
  validation step was skipped.
