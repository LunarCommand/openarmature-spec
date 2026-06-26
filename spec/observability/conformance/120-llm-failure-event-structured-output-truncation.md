# 120 — `LlmFailedEvent` response-side surface on structured-output truncation

Verifies graph-engine §6's `LlmFailedEvent` response-side surface (per proposal 0082) on the
truncation use case: a `structured_output_invalid` failure where the model hit `max_tokens` and the
JSON was cut off mid-output (`finish_reason == "length"`). This is the one llm-provider §7 category
where the provider returned a response, so the failure event carries the same five response-side
fields the success variant carries — populated from the received (but unparseable) response.

**Spec sections exercised:**

- graph-engine §6 — `LlmFailedEvent` response-side surface (`output_content`, `finish_reason`,
  `usage`, `response_id`, `response_model`), populated only for `structured_output_invalid`
  (proposal 0082).
- observability §5.5.7 — the carve-out: response-side fields present for
  `structured_output_invalid`.
- llm-provider §7 — `structured_output_invalid` raised when returned content fails parse/validation;
  §6 — `"length"` finish reason (the model hit `max_tokens`).

**Cases:**

1. `llm_failure_event_structured_output_truncation` — Mock returns a 200 with truncated JSON
   (`'{"name":"Alice","age":'`), `finish_reason: "length"`, `usage.completion_tokens` at the
   configured `max_tokens` ceiling (16). `complete()` raises `structured_output_invalid`. The typed
   event carries `error_category = "structured_output_invalid"`, `finish_reason = "length"`,
   `output_content` = the verbatim truncated bytes, `usage` = the mock's literal token counts,
   `response_id` / `response_model` present. Asserts zero `LlmCompletionEvent` (0058 mutual
   exclusion) and that the exception propagates out of `complete()`.

**What passes:**

- One `LlmFailedEvent` with `error_category = "structured_output_invalid"` and `finish_reason =
  "length"`.
- `output_content` equals the verbatim truncated bytes; `usage` equals the mock's literal counts
  (`completion_tokens` at the `max_tokens` ceiling, corroborating the truncation).
- `response_id` / `response_model` present (sourced from the received response).
- Zero `LlmCompletionEvent` for the call; the exception propagates.

**What fails:**

- The response-side fields are null (the impl treated the failure as "no response received" — the
  pre-0082 behavior).
- `finish_reason` is missing or not `"length"` — the truncation triage signal is lost.
- `usage` is zero / null despite the provider returning a usage record (the cost-accounting defect
  0082 closes).
- `LlmCompletionEvent` also observed for the same call — mutual-exclusion violation.
