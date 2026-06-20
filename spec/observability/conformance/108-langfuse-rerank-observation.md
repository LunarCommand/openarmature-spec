# 108 — Langfuse rerank observation mapping

Verifies observability §8.4.7's Langfuse mapping: `RerankProvider.rerank()` calls render as a
dedicated `Retriever` observation type (created via `asType="retriever"`), NOT a `Generation`, with
`model` / `usageDetails` / `metadata` always populated and `input` / `output` gated by
`disable_provider_payload`.

**Spec sections exercised:**

- observability §8.4.7 — Langfuse `Retriever` observation; field mappings (`model`,
  `usageDetails.searchUnits`, identity metadata, payload-gated `input` / `output`).

**Cases:**

1. `rerank_observation_payload_suppressed_by_default` — default config
   (`disable_provider_payload=True`). The `Retriever` observation emits `model` + `usageDetails`
   (`searchUnits`) + identity metadata; `input` and `output` are null. Observation type is
   `retriever`.
2. `rerank_observation_payload_emitted_with_flag_off` — `disable_provider_payload=False`. The
   observation additionally carries `input` (`{query, documents}`) and `output` (the scored results).

**What passes:**

- Observation type is `retriever` (not `generation`); `input` / `output` suppressed under default
  and populated when the flag is off.

**What fails:**

- The observation renders as `generation` or generic `span` — wrong dedicated type.
- `input` / `output` leak under the default privacy posture, or are dropped when the flag is off.
