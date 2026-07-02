# 139 — OTel embedding span omits `gen_ai.usage.input_tokens` (no-usage provider)

Verifies observability §5.5.8's **conditionally emitted** rule for `gen_ai.usage.input_tokens` on the
OTel embedding span (per proposal 0093) by exercising the observer's provider-agnostic
conditional-emission path when `EmbeddingResponse.usage = null`. With no usage record the embedding span
MUST OMIT `gen_ai.usage.input_tokens` entirely while still emitting every other attribute. The mock body
is a usage-less embedding response (the standard embedding-mock body with the `usage` block dropped) that
yields `usage = null` (retrieval-provider §4) — a harness stand-in for a no-usage provider, NOT a claim
that this is any specific vendor's wire shape. TEI `/embed` is the real-world archetype of a no-usage
embedding provider (though its actual wire is a bare vector array, a different shape than this mock).
This is the no-usage counterpart to 082 (which asserts the attribute present when the provider reports
usage).

**Spec sections exercised:**

- observability §5.5.8 — `gen_ai.usage.input_tokens` conditionally emitted (present only when a usage
  record is reported; omitted for no-usage providers such as TEI `/embed`), per the §5.5.3.1 / 0047
  conditional-emission convention.
- retrieval-provider §4 — `EmbeddingResponse.usage` is `record | null`; a provider that reports no usage
  yields `usage = null`.

**Cases:**

1. `otel_embedding_span_omits_input_tokens_when_no_usage_record` — One embedding-calling node; default
   observer config. The mocked response is a usage-less embedding body (the standard embedding-mock body
   with the `usage` block dropped) yielding `usage = null` — a harness stand-in for a no-usage provider
   (archetype: TEI `/embed`), not that vendor's exact wire. Asserts the span emits `gen_ai.system`,
   `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.response.id`,
   `openarmature.embedding.input_count`, `openarmature.embedding.dimensions`, and that
   `gen_ai.usage.input_tokens` is absent (alongside the always-deferred `gen_ai.operation.name`).

**What passes:**

- Every non-usage attribute emits with the expected value.
- `gen_ai.usage.input_tokens` is absent — no usage record to source it from.
- `gen_ai.operation.name` is absent (stable-only deferral, unchanged from 082).

**What fails:**

- `gen_ai.usage.input_tokens` emitted (e.g. fabricated as `0`) when the provider reported no usage — the
  adapter did not honor the §5.5.8 conditional-emission rule.
- A non-usage attribute dropped, or the span misnamed.
