# 079 — `EmbeddingEvent.request_params` populated with caller-supplied config

Verifies graph-engine §6's `request_params` field population on `EmbeddingEvent` (per proposal
0059). The field carries the embedding-specific runtime-config fields the caller supplied
(initially `dimensions` per retrieval-provider §2); absence-is-meaningful for unsupplied keys.
Mirrors fixture 062 for the LLM-side variant.

**Spec sections exercised:**

- graph-engine §6 — `EmbeddingEvent.request_params` field; absence-is-meaningful semantics.
- retrieval-provider §2 — `EmbeddingRuntimeConfig` shape (initially `dimensions`).

**Cases:**

1. `request_params_populates_dimensions_when_supplied` — `embed()` called with
   `config.dimensions=128`. Asserts `request_params = {dimensions: 128}`.
2. `request_params_empty_when_no_config_supplied` — `embed()` called without config. Asserts
   `request_params = {}` (empty mapping, not null).

**What passes:**

- The mapping carries supplied keys and only supplied keys.

**What fails:**

- Default values for unsupplied keys are populated — absence-is-meaningful broken.
- The field is null when no config was supplied — should be an empty mapping per the
  absence-is-meaningful contract.
