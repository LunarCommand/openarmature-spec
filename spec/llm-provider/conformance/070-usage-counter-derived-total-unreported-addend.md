# 070 — Derived `total_tokens` with an unreported addend

Verifies the llm-provider §7 *Malformed usage counter* rule composed with §8.2's **derived** `total_tokens`. The Anthropic Messages mapping returns `input_tokens` / `output_tokens` and no wire `total_tokens`, deriving the total as the sum. When an addend is not reported (here `input_tokens` is malformed), the derived total is **itself** not reported (`null`) — a mapping MUST NOT substitute the surviving addend, which would report a figure the provider never sent.

**Spec sections exercised:**

- llm-provider §7 *Malformed usage counter* — a malformed `input_tokens` is nulled; MUST NOT raise; MUST NOT coerce / repair.
- llm-provider §8.2.2 Response mapping — `usage.prompt_tokens ← input_tokens`, `usage.completion_tokens ← output_tokens`, `usage.total_tokens ←` the derived sum; a derived total whose addend is not reported is itself `null`, never the surviving addend.

**Scenario:**

The mock (`mapping: anthropic`) returns `usage: {input_tokens: "abc", output_tokens: 7}` with no wire total.

**What passes:**

- `Response.usage.prompt_tokens` is `null` (malformed `input_tokens`).
- `Response.usage.completion_tokens` is `7` (sound `output_tokens` stands).
- `Response.usage.total_tokens` is `null` — the derived total, because its `prompt_tokens` addend is not reported.
- `complete()` does not raise; `raw.usage` preserves `input_tokens: "abc"` verbatim. `raw_check.required_keys` asserts only that `usage` is **present** on `raw`; the verbatim value is pinned by the adapter-enforced invariant `raw_usage_input_tokens_verbatim_malformed`.

**What fails:**

- **The discriminator:** the mapping substitutes the surviving addend as the total — `total_tokens: 7` — which understates the true count with a figure the provider never sent.
- The implementation raises over the malformed `input_tokens`, or coerces / repairs it.
- The implementation nulls `completion_tokens` (the sound addend) or the whole record.

> The typed graph-engine §6 `LlmCompletionEvent.usage` mirrors this response (present record; `prompt_tokens` null, `completion_tokens` 7, `total_tokens` null); that mirror is asserted in the observability conformance suite.
