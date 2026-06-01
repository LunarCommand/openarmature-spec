# 042 — LLM cache attribute reported zero (distinct from absent)

Verifies §5.5.3.1's "reported miss" semantics — when the LLM provider's response carries the
cache field with value `0` (the provider explicitly reported zero cache-hit tokens, i.e., the
prompt was eligible for cache reporting but produced no hits), the §6
`Response.usage.cached_tokens` is `0` (not `null`) and the OTel observer emits
`openarmature.llm.cache_read.input_tokens = 0` on the LLM provider span. This is observably
distinct from fixture 041's absent case (provider did not report cache statistics at all).

**Spec sections exercised:**

- §5.5.3.1 — OA-namespaced cache attributes; "reported miss" case (`0`) emits the attribute
  with value `0` (not omission).
- llm-provider §6 — `Response.usage.cached_tokens` `0` vs `null` distinction.
- llm-provider §8.1.2 — OpenAI-compatible cache-stat source row; the
  `prompt_tokens_details.cached_tokens: 0` case is observable separately from "field absent".

**What passes:**

- The §6 `Response.usage.cached_tokens` is `0` (the provider's response carried
  `prompt_tokens_details.cached_tokens: 0`).
- The LLM provider span emits `openarmature.llm.cache_read.input_tokens = 0`.
- The LLM provider span does NOT emit `openarmature.llm.cache_creation.input_tokens` (OpenAI
  leaves the cache-creation field absent per §8.1.2).

**What fails:**

- The implementation conflates `0` with absent and either: omits the attribute, or sets the §6
  field to `null` instead of `0`. The absent-vs-zero distinction MUST be preserved through
  both the §6 typed field and the §5.5.3.1 span attribute.
