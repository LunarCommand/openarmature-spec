# 069 — Malformed usage counter (all three)

Verifies the llm-provider §7 *Malformed usage counter* rule when **every** counter is malformed. With no usage reported, §6's "the first three MUST be `null` together" fires as written: `Response.usage` is a **present** record of `{null, null, null}` — never a null `usage` record (the §6 record is always present), and never a raise. The three malformation kinds §7 enumerates are each exercised: a non-integer string, a negative, a boolean.

**Spec sections exercised:**

- llm-provider §7 *Malformed usage counter* — each malformed counter is nulled; MUST NOT raise; MUST NOT coerce / clamp / repair.
- llm-provider §6 `Response.usage` — the null-together clause applies because no usage is reported; the record stays present (a present record of null counters, exactly as for absent usage — cf. fixture 006 `usage_absent`).

**Scenario:**

The mock returns `usage: {prompt_tokens: "abc", completion_tokens: -5, total_tokens: true}`. The assistant `message` (`"Done."`) and `finish_reason` (`stop`) are intact.

**What passes:**

- `Response.usage` is `{prompt_tokens: null, completion_tokens: null, total_tokens: null}` — a present record.
- `complete()` does not raise.
- `raw.usage` preserves all three malformed values verbatim (the string, the negative, and the boolean). `raw_check.required_keys` asserts only that `usage` is **present** on `raw`; the verbatim values are pinned by the adapter-enforced invariant `raw_usage_all_counters_verbatim_malformed`.

**What fails:**

- The implementation raises `provider_invalid_response` over the malformed counters.
- The implementation returns a **null** `usage` record instead of a present record of null counters (this is the shape 0101 pins — the response and its observability event must agree).
- The implementation coerces / clamps / repairs any counter, or defaults to `0`.
- `raw.usage` no longer carries the verbatim malformed values.

> The typed graph-engine §6 `LlmCompletionEvent.usage` mirrors this response — a **present record of null counters**, not a null `usage`; that mirror is asserted in the observability conformance suite.
