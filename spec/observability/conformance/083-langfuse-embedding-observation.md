# 083 — Langfuse `Embedding` observation rendering

Verifies observability §8's Langfuse mapping for `EmbeddingProvider.embed()` calls (per
proposal 0059). Embedding calls map onto Langfuse's dedicated `Embedding` observation type
(created via `asType: "embedding"`), NOT `Generation` with an operation discriminator. The
`disable_provider_payload` flag gates both the `input` strings list and the `output` vectors
on the same footing — vectors are payload-bearing per the vec2text-aware privacy posture
documented in proposal 0059's *Privacy posture for embedding observations* section.

**Spec sections exercised:**

- observability §8 — embedding observation mapping (proposal 0059).
- observability §5.5.4 — `disable_provider_payload` flag (renamed from `disable_llm_payload`
  by proposal 0059; covers payload from any provider call).

**Cases:**

1. `embedding_observation_payload_suppressed_by_default` — Default observer config
   (`disable_provider_payload=True`). Asserts the observation type is `embedding`, `model` +
   `usageDetails` + identity metadata are populated, and `input` + `output` are null
   (payload-gated).
2. `embedding_observation_payload_emitted_with_flag_off` — `disable_provider_payload=False`.
   Asserts the same shape PLUS `input` carries the strings list and `output` carries the full
   vectors.

**What passes:**

- Observation type is `embedding` (not `generation`).
- Privacy posture matches the flag: payload absent under default, fully populated under
  flag-off.

**What fails:**

- Observation type is `generation` with a metadata discriminator — the adapter implemented the
  pre-proposal-0059 mapping shape.
- Payload populated under `disable_provider_payload=True` — default-conservative privacy
  posture broken.
- Payload still null under `disable_provider_payload=False` — flag does not gate the field
  surface.
