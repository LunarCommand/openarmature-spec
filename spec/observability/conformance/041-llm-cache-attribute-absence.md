# 041 — LLM cache attribute absence (no cache field)

Verifies §5.5.3.1's conditional-emission convention — when the LLM provider's response does
NOT carry the OpenAI-compatible cache field (e.g., a vLLM server without
`--enable-prompt-tokens-details`, or any provider not reporting cache stats), the OTel observer
MUST NOT emit `openarmature.llm.cache_read.input_tokens` or
`openarmature.llm.cache_creation.input_tokens` on the LLM provider span. Attribute absence is
the spec-canonical signal for "the provider did not report this", distinct from
"the provider reported zero" (which would emit the attribute with value 0).

**Spec sections exercised:**

- §5.5.3.1 — OA-namespaced cache attributes; conditional emission gated on §6
  `Response.usage.cached_tokens` / `cache_creation_tokens` being populated.
- llm-provider §6 — `Response.usage.cached_tokens` is `null` when the provider does not
  report; the spec distinguishes absent (no report) from `0` (reported zero).
- llm-provider §8.1.2 — vLLM dual-flag caveat (cache stats are absent when
  `--enable-prompt-tokens-details` is off).

**What passes:**

- The §6 `Response.usage.cached_tokens` is `null` (the provider response has no
  `prompt_tokens_details` block).
- The LLM provider span does NOT emit `openarmature.llm.cache_read.input_tokens`.
- The LLM provider span does NOT emit `openarmature.llm.cache_creation.input_tokens`.

**What fails:**

- The implementation emits `openarmature.llm.cache_read.input_tokens = 0` when the §6 field is
  absent — conflates "absent" with "zero", defeating the absent-vs-zero distinction.
- The implementation defaults to `0` instead of leaving the §6 field as `null` when the
  provider does not surface the field.
