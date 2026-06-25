# 122 — `LlmFailedEvent` response-side surface null on a non-body failure

Verifies graph-engine §6's rule (per proposal 0082) that the `LlmFailedEvent` response-side surface
is populated **only** for `structured_output_invalid` — the one llm-provider §7 category where the
provider returned a response. For every other category, no response was received, so all five
response-side fields are null. This locks the carve-out against the companion truncation /
schema-mismatch fixtures (120 / 121).

**Spec sections exercised:**

- graph-engine §6 — the response-side surface (`output_content`, `finish_reason`, `usage`,
  `response_id`, `response_model`) is null for every §7 category except `structured_output_invalid`
  (proposal 0082).
- observability §5.5.7 — "response-side fields are absent for the categories where no response was
  received."
- llm-provider §7 — `provider_unavailable` (a 503; no usable response body).

**Cases:**

1. `llm_failure_event_response_side_null_on_non_body_failure` — Mock returns a 503; the impl
   classifies it `provider_unavailable`. `complete()` raises. The typed event carries
   `error_category = "provider_unavailable"` and all five response-side fields null
   (`output_content`, `finish_reason`, `usage`, `response_id`, `response_model`). The exception
   propagates.

**What passes:**

- One `LlmFailedEvent` with `error_category = "provider_unavailable"`.
- All five response-side fields null.
- The exception propagates out of `complete()`.

**What fails:**

- Any response-side field populated (e.g., a fabricated zero `usage` or empty `output_content`) —
  the surface must be null for a category that received no response, the inverse of the
  `structured_output_invalid` carve-out.
- `error_category` missing or non-§7.
