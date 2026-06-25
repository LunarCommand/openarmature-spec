# 124 — OTel error span renders output / usage / finish_reason

Verifies observability §5.5.1 / §5.5.3 (per proposal 0082): on a `structured_output_invalid`
failure, the OTel LLM error span carries the same response-side surface a success span carries —
`openarmature.llm.output.content` (from `output_content`, payload-gated), `openarmature.llm.finish_reason`,
and the `openarmature.llm.usage.*` token attributes — additively. No new attribute names are
introduced (the success-path attributes populate on the error span). Span status stays `ERROR` with
the §4.2 exception event. Runs the fixture-120 truncation case through the OTel observer.

**Spec sections exercised:**

- observability §5.5.1 — `openarmature.llm.output.content` (payload-gated per §5.5.4) on the error
  span (proposal 0082).
- observability §5.5.3 — `openarmature.llm.finish_reason` + `openarmature.llm.usage.*` on the error
  span (not payload-gated).
- observability §4.2 — span `ERROR` status + recorded exception event + `openarmature.error.category`
  (unchanged; the response-side attributes are additive).

**Cases:**

1. `otel_error_span_renders_output_usage_finish_reason_payload_on` — Truncation failure
   (`finish_reason: "length"`, `usage.completion_tokens` at the `max_tokens` ceiling) with
   `disable_provider_payload = False`. The `openarmature.llm.complete` span is `ERROR` with
   `status_description = "structured_output_invalid"` + a recorded exception AND carries
   `openarmature.llm.output.content` (the raw bytes), `openarmature.llm.finish_reason = "length"`,
   and `openarmature.llm.usage.{prompt,completion,total}_tokens`.
2. `otel_error_span_payload_disabled_redacts_output_keeps_usage_finish_reason` — The same failure
   with the default `disable_provider_payload = True`. `openarmature.llm.output.content` is absent,
   while `openarmature.llm.finish_reason`, the `openarmature.llm.usage.*` attributes, the `ERROR`
   status, and the recorded exception are unchanged.

**What passes:**

- Case 1: the error span carries the response-side surface on the success-path attribute names,
  with `ERROR` status + exception event preserved.
- Case 2: `output.content` is suppressed under the payload-disabled flag; `finish_reason`, the
  `usage.*` attributes, the `ERROR` status, and the exception event survive.

**What fails:**

- The error span lacks the response-side attributes despite a `structured_output_invalid` failure
  carrying a response (the pre-0082 behavior).
- A new attribute name is introduced for the failed output instead of reusing
  `openarmature.llm.output.content` (0082 reuses the success-path attributes).
- The span status drops to `OK`, or the exception event is omitted, when the response attributes
  populate (status / exception are unchanged).
- Case 2: `finish_reason` or `usage.*` is suppressed along with `output.content` (only the payload
  attribute is gated), or `output.content` survives the payload-disabled flag.
