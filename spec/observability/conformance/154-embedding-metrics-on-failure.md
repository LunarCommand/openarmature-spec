# 154 — embedding metrics on failure (duration + `error.type`, no `token.usage`)

Closes the embedding-path counterpart of the LLM failure-metrics fixture 090. §11 records
`openarmature.gen_ai.client.operation.duration` on **every** attempt including failures (with `error.type` = the
§7 category from the typed `EmbeddingFailedEvent`), and records **no** `token.usage` observation on a failure
(no usage record to source). The shipped embedding-metrics fixtures (089 usage, 143 no-usage) were both success
`EmbeddingEvent`s, so the embedding failure-duration path was normatively required yet conformance-untested — a
`v0.103.1` PATCH pins it (no new spec).

**Spec sections exercised:**

- observability §11.2 / §11.3 — duration recorded on a failed attempt, `error.type` dimension from the typed
  `EmbeddingFailedEvent`; `operation="embeddings"`.
- observability §11 metric-capture — no `token.usage` observation when the call returns no usage record.

**Case:**

1. `errored_embedding_records_duration_with_error_type` — a `calls_embed` node with `enable_metrics=True`;
   the mock returns 503 → `provider_unavailable`, `embed()` raises. The duration histogram records one
   observation with `error.type="provider_unavailable"` (operation `embeddings`); no `token.usage` observation.

**What fails:**

- Not recording a duration observation for a failed embedding attempt, omitting/mis-sourcing `error.type`, using
  the wrong `operation` dimension, or recording a `token.usage` observation on a failure (no usage record).
