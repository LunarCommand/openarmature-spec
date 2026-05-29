# 038 — Anthropic max_tokens required

Verifies the §8.2.1 `max_tokens` requirement.

**Spec sections exercised:**

- §8.2.1 — Anthropic requires `max_tokens` on every request; when `RuntimeConfig.max_tokens` is
  absent the mapping raises `provider_invalid_request` at pre-send validation rather than
  defaulting to a magic value.

**Cases:**

1. `missing_max_tokens_raises` — no `max_tokens` supplied → `provider_invalid_request`.
2. `present_max_tokens_proceeds` — `max_tokens: 100` supplied → the call proceeds and the value
   appears on the wire.

**What fails:**

- A call without `max_tokens` proceeds (the mapping invented a default) instead of raising.
- A call without `max_tokens` reaches the wire (Anthropic would 400, but the spec mandates
  pre-send rejection).
