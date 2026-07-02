# 140 — Langfuse embedding observation omits `usageDetails.input` (no-usage provider)

Verifies observability §8.4.5's **when populated / omitted when no usage record** rule for
`embedding.usageDetails.input` (per proposal 0093) by exercising the observer's provider-agnostic
conditional path when `EmbeddingResponse.usage = null`. With no usage record the `Embedding`
observation's `usageDetails` MUST NOT carry an `input` key. The mock body is a usage-less embedding
response (the standard embedding-mock body with the `usage` block dropped) that yields `usage = null`
(retrieval-provider §4) — a harness stand-in for a no-usage provider, NOT a claim that this is any
specific vendor's wire shape. TEI `/embed` is the real-world archetype of a no-usage embedding provider
(though its actual wire is a bare vector array, a different shape than this mock). This is the no-usage
counterpart to 083 (which populates `usageDetails.input` when the provider reports usage).

**Spec sections exercised:**

- observability §8.4.5 — `embedding.usageDetails.input` populated only when a usage record is reported;
  omitted when the embedding call reports no usage record (`usage = null`, e.g. TEI `/embed`).
- retrieval-provider §4 — `EmbeddingResponse.usage` is `record | null`; a provider that reports no usage
  yields `usage = null`.

**Cases:**

1. `embedding_observation_omits_usagedetails_input_when_no_usage_record` — Default observer config
   (`disable_provider_payload=True`). The mocked response is a usage-less embedding body (the standard
   embedding-mock body with the `usage` block dropped) yielding `usage = null` — a harness stand-in for
   a no-usage provider (archetype: TEI `/embed`), not that vendor's exact wire. Asserts the observation
   type is `embedding`, `model` + identity metadata are populated, `usageDetails` carries no `input` key
   (encoded as an empty map, mirroring 108's idiom of populating `usageDetails` with only the keys the
   provider reported), and `input` / `output` stay null under the default payload posture.

**What passes:**

- Observation type is `embedding` (not `generation`).
- `usageDetails` carries no `input` key — no usage record to source it from.
- `model` + identity metadata populated; `input` / `output` null under the default posture.

**What fails:**

- `usageDetails.input` populated (e.g. fabricated as `0`) when the provider reported no usage — the
  adapter did not honor the §8.4.5 omission rule.
- Observation renders as `generation`, or `model` / metadata dropped.
