# 079 — §8.2 Anthropic `stop_sequences` merge (array-only, no coercion)

Exercises the merge arm of §6 clause (b) on the Anthropic mapping — the mapping-specific counterpart to the
OpenAI `stop` merge (fixture 076). Anthropic realizes the declared `stop_sequences` under the **same wire name**
(no rename), and it is **array-only**: unlike OpenAI's string-or-array `stop`, there is no scalar-string coercion
arm. A colliding extras `stop_sequences` merges (declared first, de-duplicated).

**Spec sections exercised:**

- llm-provider §6 clause (b) — merge arm for a list-shaped declared-field realization.
- llm-provider §8.2 — `stop_sequences` realized under Anthropic's native name; array-only (no scalar coercion).

**Cases:**

1. `extras_stop_sequences_merges_with_declared` — `["STOP"]` + extras `["END"]` → wire `["STOP", "END"]`.
2. `matching_extras_stop_sequences_collapses_dedup` — `["STOP"]` + extras `["STOP"]` → wire `["STOP"]`.

**What fails:**

- Coercing a scalar-string extras value (that is OpenAI's behavior, not Anthropic's), letting the extras value
  win outright, dropping the declared value, or emitting a duplicated list on the matching case.
