# 147 — A not-reported counter reaches no span, histogram, or budget surface (leak-prevention)

The **point of proposal 0101**: a single completion whose `prompt_tokens` is not reported (null) reaches
**none** of the three LLM usage surfaces, asserted in one fixture — the OTel span attribute, the
token-usage histogram observation, and the token-budget instrument. This is 0101 Alternative #3's
"a rule an observer routes around is not a rule": before this proposal the guards keyed on the usage
**record** being null, so a null **counter** inside a present record slipped past all three surfaces.

One node renders a budgeted prompt (`input_max_tokens` 10) and calls the LLM; `enable_metrics=True`;
default OTel observer. Mock usage `{prompt_tokens: null, completion_tokens: 5, total_tokens: 15}` — the
`{null, 5, 15}` record of 0101 (malformed `prompt_tokens` nulled per llm-provider §7 *Malformed usage
counter*). The wire carries `prompt_tokens: null` directly (the post-nulling state); this fixture renders
a null counter, it does not test the wire-malformed → `null` mapping (sibling llm-provider fixture).

The sound **output** and **total** counters ride every surface normally — the omission is **per-field**,
isolated to the null `prompt_tokens`: the span still emits `gen_ai.usage.output_tokens` /
`openarmature.llm.usage.total_tokens`, and the histogram still records the `"output"` observation.

**Spec sections exercised:**

- observability §5.5.3 — the span omits both input usage attributes on the null counter (per-field).
- observability §11.2 — the histogram records no `"input"` observation; the token-budget instruments do
  not evaluate the unevaluable input bound.
- observability §5.5.15 — the `openarmature.llm.token_budget.exceeded` span signal is not set (absent,
  not `false`) when its only declared bound's counter is not reported.
- graph-engine §6 (proposal 0101) — `LlmCompletionEvent.usage` mirrors the response (present record,
  null counter) — the single source all surfaces read and all omit.
- llm-provider §7 *Malformed usage counter* — a malformed counter is not reported.

**Cases:**

1. `null_prompt_tokens_reaches_no_span_histogram_or_budget_surface` — composes fixtures 144 (span), 145
   (histogram), and 146 case A (budget) into one assertion, so the three surfaces are proven to omit the
   **same** null counter together. Asserts: the span omits `gen_ai.usage.input_tokens`,
   `openarmature.llm.usage.prompt_tokens`, and `openarmature.llm.token_budget.exceeded`, while emitting
   the sound output / total attributes and the declared budget; the metrics set is the `"output"`
   token.usage observation plus one duration observation — no `"input"` observation, and neither
   token-budget instrument recorded.

**Harness note.** The three-surface combination composes in one fixture because the default OTel observer
(`span_tree`), `enable_metrics` (`metrics`), and a declared `token_budget` all coexist. The **Langfuse
`Generation`** surface is the fourth LLM usage surface; it requires a separate observer configuration and
is covered by fixture 148 (`generation.usage.input` omitted on the same null counter).

**What passes:**

- Span: both input usage attributes absent; the exceeded budget signal absent; output / total present.
- Histogram: only the `"output"` token.usage observation; no `"input"` observation.
- Budget: neither `token_budget.utilization` nor `token_budget.exceeded` recorded.

**What fails:**

- Any surface emitting from the null counter — an `input_tokens` span attribute, an `"input"` histogram
  observation, or a budget `utilization` / `exceeded` observation over the null. Each is a leak 0101
  closes.
