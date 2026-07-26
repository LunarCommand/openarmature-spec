# 080 — §8.3 Gemini `stopSequences` merge (camelCase under `generationConfig`)

Exercises the merge arm of §6 clause (b) on the Gemini mapping — the mapping-specific counterpart to OpenAI's
`stop` (076, at the request root) and Anthropic's `stop_sequences` (079, at the root). Gemini nests sampling
parameters (and undeclared extras) under `generationConfig`, so the declared `stop_sequences` is realized as
`generationConfig.stopSequences` and a colliding extras `stopSequences` merges **there**, not at the request
root. Array-only (no scalar coercion).

**Spec sections exercised:**

- llm-provider §6 clause (b) — merge arm for a list-shaped declared-field realization.
- llm-provider §8.3 — `stop_sequences` realized as `generationConfig.stopSequences` (camelCase); the colliding
  extras key is the camelCase name under `generationConfig`.

**Cases:**

1. `extras_stopSequences_merges_under_generationConfig` — `["STOP"]` + extras `["END"]` →
   `generationConfig.stopSequences: ["STOP", "END"]`.
2. `matching_extras_stopSequences_collapses_dedup` — `["STOP"]` + extras `["STOP"]` →
   `generationConfig.stopSequences: ["STOP"]`.

**What fails:**

- Merging at the request root instead of under `generationConfig`, coercing a scalar string (Gemini is
  array-only), letting the extras value win, or emitting a duplicated list on the matching case.
