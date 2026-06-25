# 023 — Structured Output Schema Validation Failure

`complete()` called with a `response_schema`; provider returns valid
JSON, but the JSON fails to validate against the schema (missing
required field). MUST raise `structured_output_invalid`. Verifies the
validation-failure half of §7's `structured_output_invalid` semantics,
complementing the parse-failure case in fixture 022.

**Spec sections exercised:**

- §7 `structured_output_invalid` — raised when the provider's content
  parses as JSON but fails to validate against the supplied schema.
- §7 error payload — failure description SHOULD identify the failing
  field/pointer; the error also exposes the response's normalized
  `finish_reason` and token `usage` (per proposal 0082).

**What passes:**

- `complete()` raises `structured_output_invalid`.
- The error payload carries the requested schema and the raw response
  content (`'{"name":"Alice"}'`).
- The failure description mentions the missing `"age"` field.
- The error also carries the response's `finish_reason` (`"stop"`) and
  `usage` (the body's literal token counts), per proposal 0082.

**What fails:**

- A different error category is raised.
- The error payload doesn't identify the failing field — would make the
  error harder to debug.
- The error payload is missing the now-required `finish_reason` or
  `usage`.
- The call returns normally with `parsed` set to the missing-field state
  — would mean the validation step accepted a non-conformant value.
