# 048 — Gemini RuntimeConfig field mapping

Verifies §8.3.1 — all seven §6 declared `RuntimeConfig` fields map under `generationConfig`.

**Spec sections exercised:**

- §8.3.1 RuntimeConfig mapping — `temperature` → `temperature`, `top_p` → `topP`, `max_tokens` →
  `maxOutputTokens`, `stop_sequences` → `stopSequences`, `seed` → `seed`, `frequency_penalty` →
  `frequencyPenalty`, `presence_penalty` → `presencePenalty`.

**What passes:**

- All seven declared fields appear under `generationConfig` with the Gemini wire names.
- `frequency_penalty` / `presence_penalty` map directly (no rejection), unlike the §8.2 Anthropic
  mapping which lacks them.

**What fails:**

- Any field emitted at the request root instead of under `generationConfig`.
- `frequency_penalty` / `presence_penalty` raising `provider_invalid_request` (the Anthropic
  behavior) instead of mapping to `frequencyPenalty` / `presencePenalty`.
- `max_tokens` emitted as `max_tokens` / `maxTokens` instead of `maxOutputTokens`.
