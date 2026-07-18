# 068 — Malformed usage counter (partial)

Verifies the llm-provider §7 *Malformed usage counter* rule for a partially-malformed usage record: a counter present on the wire but malformed (a non-integer, a negative, a boolean) is treated as **not reported** — that counter is `null`, the other counters stand, the record is still present, and `complete()` does **not** raise. The verbatim malformed value survives on `Response.raw`.

**Spec sections exercised:**

- llm-provider §7 *Malformed usage counter* — a malformed `prompt_tokens` is nulled; MUST NOT raise `provider_invalid_response` (or any category) because of the counter; MUST NOT coerce, clamp, or repair it.
- llm-provider §6 `Response.usage` — the per-field `null` §6 permits; "the first three MUST be `null` together" is conditioned on *no* usage being reported, which a partially-malformed record does not satisfy, so the outcome is `{null, 50, 150}`, not `{null, null, null}`.
- llm-provider §8.1 — OpenAI-compatible mapping (the default); `total_tokens` is a sound wire total that stands even though `prompt_tokens` is nulled.

**Scenario:**

The mock returns a completion whose `usage` is `{prompt_tokens: "abc", completion_tokens: 50, total_tokens: 150}`. The assistant `message` (`"Hello."`) and `finish_reason` (`stop`) are intact.

**What passes:**

- `Response.usage.prompt_tokens` is `null`; `completion_tokens` is `50`; `total_tokens` is `150`; the record is present.
- `message` and `finish_reason` are unchanged — the completion succeeded.
- `complete()` does not raise.
- `raw.usage` preserves the malformed `"abc"` verbatim. `raw_check.required_keys` asserts only that `usage` is **present** on `raw`; the verbatim value is pinned by the adapter-enforced invariant `raw_usage_prompt_tokens_verbatim_malformed`.

**What fails:**

- The implementation raises `provider_invalid_response` over the malformed counter (discards a sound completion).
- The implementation coerces / clamps / repairs `"abc"` to an integer (fabrication), or defaults it to `0`.
- The implementation nulls the whole `usage` record, discarding the sound `completion_tokens` / `total_tokens`.
- `raw.usage` no longer carries the verbatim `"abc"`.

> The typed graph-engine §6 `LlmCompletionEvent.usage` mirrors this response (present record, `prompt_tokens` null); that mirror is asserted in the observability conformance suite, which renders the §5.5.3 usage attributes from the event.
