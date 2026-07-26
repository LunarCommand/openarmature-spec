# 037 — Anthropic RuntimeConfig mapping

Verifies the §8.2.1 RuntimeConfig field mapping for Anthropic.

**Spec sections exercised:**

- §8.2.1 RuntimeConfig mapping: `temperature`, `top_p`, `stop_sequences`, `max_tokens`
  map directly. `stop_sequences` keeps its name (no rename — unlike OpenAI's `stop`).
- §8.2.1 — `seed`, `frequency_penalty`, `presence_penalty` are unsupported by Anthropic (its
  Messages API has no `seed` or penalty parameters); supplying them raises `provider_invalid_request`
  at pre-send validation (quiet drop forbidden).

**Cases:**

1. `supported_declared_fields_map_directly` — the four supported declared fields appear on the
   wire verbatim; `stop_sequences` is NOT renamed.
2. `frequency_penalty_rejected` — supplying `frequency_penalty` raises `provider_invalid_request`.
3. `presence_penalty_rejected` — supplying `presence_penalty` raises `provider_invalid_request`.
4. `seed_rejected` — supplying `seed` (no Anthropic wire parameter) raises `provider_invalid_request`.

**What fails:**

- `stop_sequences` renamed to `stop` (that is OpenAI's wire key, not Anthropic's).
- `seed` / `frequency_penalty` / `presence_penalty` silently dropped or forwarded to the wire
  instead of raising `provider_invalid_request` (Anthropic has no such wire parameters).
