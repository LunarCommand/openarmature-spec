# 040 — LLM cache attribute emission (cache hit)

Verifies §5.5.3.1 *OA-namespaced cache attributes (stable-only mirror)* — when the LLM
provider's response carries the OpenAI-compatible cache field
`usage.prompt_tokens_details.cached_tokens = N` (N > 0), the OTel observer emits
`openarmature.llm.cache_read.input_tokens = N` on the LLM provider span. The
`openarmature.llm.cache_creation.input_tokens` attribute is absent (OpenAI-compatible providers
do not populate the §6 `Response.usage.cache_creation_tokens` field per §8.1.2).

**Spec sections exercised:**

- §5.5.3.1 — OA-namespaced cache attributes; conditional emission gated on §6
  `Response.usage.cached_tokens` being populated.
- llm-provider §6 — `Response.usage.cached_tokens` field.
- llm-provider §8.1.2 — OpenAI-compatible cache-stat source row
  (`usage.prompt_tokens_details.cached_tokens`).

**What passes:**

- The §6 `Response.usage.cached_tokens` equals `N` (sourced from the OpenAI-compatible
  `prompt_tokens_details.cached_tokens` per §8.1.2).
- The LLM provider span emits `openarmature.llm.cache_read.input_tokens = N`.
- The LLM provider span does NOT emit `openarmature.llm.cache_creation.input_tokens` (OpenAI
  leaves the §6 cache-creation field absent per §8.1.2).

**What fails:**

- The attribute is missing despite the provider populating the cache field — implementation
  did not source from `prompt_tokens_details.cached_tokens` or did not project the §6 field to
  the §5.5.3.1 attribute.
- The implementation emits the upstream Development-status `gen_ai.usage.cache_read.input_tokens`
  attribute name instead of the OA-namespaced one (the stable-only policy requires
  OA-namespace until upstream stabilizes).
- The implementation emits `openarmature.llm.cache_creation.input_tokens` despite the OpenAI
  provider not sourcing that field.
