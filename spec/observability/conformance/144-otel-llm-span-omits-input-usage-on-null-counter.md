# 144 — OTel LLM span omits input usage attributes on a not-reported `prompt_tokens`

Verifies observability §5.5.3's **per-field** omit-guard for the LLM usage attributes (per proposal
0101) by exercising the observer's rendering of a `Response.usage` record whose `prompt_tokens` counter
is **not reported** — `{prompt_tokens: null, completion_tokens: 5, total_tokens: 15}`, the `{null, 5, 15}`
partial-malformed record of 0101 (a provider that reported a malformed `prompt_tokens`, nulled per
llm-provider §7 *Malformed usage counter*, beside two sound counters). The span MUST omit **both** input
usage attributes — `gen_ai.usage.input_tokens` and its declared mirror
`openarmature.llm.usage.prompt_tokens` — while still emitting the sound output pair and the total.

The mock's wire `usage` carries `prompt_tokens: null` directly: the post-nulling state of a malformed
counter (llm-provider §6 types each counter as "a non-negative integer or `null`"). This fixture renders
a null counter; it does **not** test the wire-malformed → `null` mapping, which the sibling llm-provider
fixtures cover.

**Why it bites (the reversal 0101 pins).** §5.5.3's `gen_ai.usage.input_tokens` guard moved from
per-**record** ("omit when the usage record is null", proposal 0093) to per-**field** ("omit when the
counter is null"). Here the record is present (two sound counters), so a per-record implementation would
emit `gen_ai.usage.input_tokens` sourced from a null counter, while its mirror
`openarmature.llm.usage.prompt_tokens` (already per-field) omits — breaking the spec's "both emit"
pairing and leaving one of the pair undefined. Asserting both input attributes absent catches that impl.

**Spec sections exercised:**

- observability §5.5.3 — `gen_ai.usage.input_tokens` / `openarmature.llm.usage.prompt_tokens` omitted
  per-field when `prompt_tokens` is not reported; `gen_ai.usage.output_tokens` /
  `openarmature.llm.usage.completion_tokens` / `openarmature.llm.usage.total_tokens` emit when their
  counters are sound.
- llm-provider §7 *Malformed usage counter* — a malformed counter is not reported (that counter is
  `null`); the others stand. The `{null, 5, 15}` outcome of proposal 0101.

**Cases:**

1. `otel_llm_span_omits_input_usage_attributes_when_prompt_tokens_null` — one LLM-calling node; default
   OTel observer. Mock usage `{null, 5, 15}`. Asserts the span omits `gen_ai.usage.input_tokens` and
   `openarmature.llm.usage.prompt_tokens` (via `attributes_absent`), emits `gen_ai.usage.output_tokens`
   = 5, `openarmature.llm.usage.completion_tokens` = 5, `openarmature.llm.usage.total_tokens` = 15, and
   the identity attributes.

**What passes:**

- Both input usage attributes are absent — the null counter reaches neither.
- The output pair and the total attribute emit with the sound values.
- Identity attributes (`gen_ai.system`, request/response model, response id, finish reasons) emit
  unchanged.

**What fails:**

- `gen_ai.usage.input_tokens` emitted (fabricated, e.g. `0` or `null`-typed) from the null counter — a
  per-record impl that did not adopt the §5.5.3 per-field guard.
- `openarmature.llm.usage.prompt_tokens` emitted from the null counter.
- The output or total attribute dropped, or the span misnamed.
