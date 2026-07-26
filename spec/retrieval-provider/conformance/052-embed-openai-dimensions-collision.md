# 052 — `dimensions` same-name collision (OpenAI-compatible embeddings)

Pins the retrieval same-name declared-field realization arm of §6 clause (b) (inherited via §10) — the analogue
of the llm `temperature` collision (fixture 075). §8.3 realizes the declared `dimensions` as the wire
`dimensions` field (same name); while the caller sets it the wire key is a **managed non-additive scalar**: a
conflicting extras `dimensions` is rejected pre-send, a matching one is a no-op. This exercises §10's reconciled
clause — a key whose *name* matches a declared field's wire realization may appear in the extras bag as an
undeclared colliding key.

**Spec sections exercised:**

- llm-provider §6 clause (b) (inherited by retrieval §10) — same-name declared-field realization, non-additive.
- retrieval-provider §8.3 — `dimensions` realized as the OpenAI-compatible `/v1/embeddings` `dimensions` field.
- retrieval-provider §7 — `provider_invalid_request` at pre-send validation, no request issued.

**Cases:**

1. `conflicting_extras_dimensions_rejected_pre_send` — `embed(config={dimensions: 4, extras: {dimensions: 8}})`
   → `provider_invalid_request` pre-send, no request issued.
2. `matching_extras_dimensions_is_no_op` — `embed(config={dimensions: 4, extras: {dimensions: 4}})` → wire
   `dimensions: 4` once, call proceeds.

**What fails:**

- Letting a conflicting extras `dimensions` override the declared value (silent double-set), forwarding or
  dropping it, or issuing a request on the conflict case.
