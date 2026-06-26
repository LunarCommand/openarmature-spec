# 123 — Langfuse failed Generation renders output / usage / finish_reason

Verifies observability §8.4.3's *Failed Generation for `structured_output_invalid`* rule (per
proposal 0082): the bundled Langfuse observer's **failed** Generation populates the same Generation
fields a success would — `generation.output` (from `output_content`, payload-gated), `generation.usage`,
`generation.metadata.finish_reason` / `response_model` / `response_id` — **in addition to** its
`level = "ERROR"` + `openarmature.error.category` mapping (§8.4.2), not in place of it. Runs the
fixture-120 truncation case through the Langfuse observer.

**Spec sections exercised:**

- observability §8.4.3 — *Failed Generation for `structured_output_invalid`* (proposal 0082): the
  failed Generation carries `output` / `usage` / `metadata.finish_reason` from the `LlmFailedEvent`
  response-side surface, alongside the §8.4.2 ERROR-level mapping.
- observability §8.4.2 — `openarmature.error.category` → `observation.level = "ERROR"`,
  `observation.statusMessage = <category>`.
- observability §5.5.4 — `disable_provider_payload` gates `generation.output` (payload-bearing);
  `usage` / `finish_reason` are not payload-gated.

**Cases:**

1. `failed_generation_renders_output_usage_finish_reason_payload_on` — Truncation failure
   (`finish_reason: "length"`, `usage.completion_tokens` at the `max_tokens` ceiling) with
   `disable_provider_payload = False`. The failed Generation carries `level = "ERROR"` +
   `statusMessage = "structured_output_invalid"` AND `generation.output` = the raw truncated bytes,
   `generation.usage` = the token counts (input 20 / output 16 / total 36), and
   `generation.metadata.finish_reason = "length"`.
2. `failed_generation_payload_disabled_redacts_output_keeps_usage_finish_reason` — The same failure
   with `disable_provider_payload = True` (the §5.5.4 default). `generation.output` is redacted
   (`null`), while `generation.usage`, `generation.metadata.finish_reason`, the `ERROR` level, and
   the `statusMessage` are unchanged.

**What passes:**

- Case 1: the failed Generation shows the raw output, real token usage, and stop reason — not the
  null / zero record the pre-0082 behavior produced — alongside the ERROR level + category.
- Case 2: `output` is redacted under the payload-disabled flag; `usage`, `finish_reason`, ERROR
  level, and `statusMessage` survive (they are not payload-gated per 0082).

**What fails:**

- The failed Generation renders `output` / `usage` as null / zero despite a
  `structured_output_invalid` failure carrying a response (the defect 0082 closes).
- The ERROR level or `statusMessage` is dropped when the response-side fields are added (they are
  additive, not a replacement).
- Case 2: `usage` or `finish_reason` is redacted along with `output` (only `output` is
  payload-gated), or `output` survives the payload-disabled flag.
