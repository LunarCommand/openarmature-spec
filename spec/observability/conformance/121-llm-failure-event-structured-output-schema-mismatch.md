# 121 — `LlmFailedEvent` response-side surface on structured-output schema mismatch

Verifies graph-engine §6's `LlmFailedEvent` response-side surface (per proposal 0082) on the
schema-mismatch case — the contrast to fixture 120's truncation. The model finished cleanly
(`finish_reason == "stop"`) but emitted valid JSON that violates the schema (a required field
missing). Pins the triage distinction that motivates 0082: `"length"` (truncation, may succeed on
retry with a larger budget) versus `"stop"` (genuine schema failure, usually fails the same way on
retry).

**Spec sections exercised:**

- graph-engine §6 — `LlmFailedEvent` response-side surface, populated for
  `structured_output_invalid` (proposal 0082).
- observability §5.5.7 — the carve-out.
- llm-provider §7 — `structured_output_invalid` on schema-validation failure; §6 — `"stop"` finish
  reason (the model finished normally).

**Cases:**

1. `llm_failure_event_structured_output_schema_mismatch` — Mock returns a 200 with valid JSON
   missing the required `"age"` field (`'{"name":"Alice"}'`), `finish_reason: "stop"`. `complete()`
   raises `structured_output_invalid`. The typed event carries `error_category =
   "structured_output_invalid"`, `finish_reason = "stop"`, `output_content` = the verbatim JSON,
   `usage` present, `response_id` / `response_model` present. Companion to fixture 120 — the `"stop"`
   vs. `"length"` contrast.

**What passes:**

- One `LlmFailedEvent` with `error_category = "structured_output_invalid"` and `finish_reason =
  "stop"` (distinct from fixture 120's `"length"`).
- `output_content` equals the verbatim JSON; `usage` present.
- `response_id` / `response_model` present.
- Zero `LlmCompletionEvent`; the exception propagates.

**What fails:**

- The response-side fields are null (pre-0082 "no response received" treatment).
- `finish_reason` is missing, or reported as `"length"` — collapsing the schema-failure case into
  the truncation case and defeating the triage distinction.
- `usage` is zero / null despite the provider returning a usage record.
- `LlmCompletionEvent` also observed — mutual-exclusion violation.
