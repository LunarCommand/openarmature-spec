# 148 — Langfuse Generation `usage` omits input on a not-reported `prompt_tokens`

Verifies observability §8.4.3's omit-on-not-reported guard for the bundled Langfuse observer's
`generation.usage` record (per proposal 0101). Unlike the `Embedding` / `Retriever` observations' open
`usageDetails` map — which already omits a not-reported figure (fixtures 140 / 142) — the `Generation`
maps the three LLM counters to a **fixed** Langfuse `Usage` record (`input` / `output` / `total`) and
carried **no** per-counter null guard before this proposal. §8.4.3 now omits each `generation.usage`
field whose source counter is not reported.

Mock usage `{prompt_tokens: null, completion_tokens: 5, total_tokens: 15}` — the `{null, 5, 15}` record
of 0101 (malformed `prompt_tokens` nulled per llm-provider §7 *Malformed usage counter*). The wire
carries `prompt_tokens: null` directly (the post-nulling state); this fixture renders a null counter, it
does not test the wire-malformed → `null` mapping (sibling llm-provider fixture). This is a **successful**
completion — the guard is on the ordinary success mapping, distinct from the failed-Generation path
(fixture 123).

This is the fourth LLM usage surface (span, histogram, and budget are fixture 147); the fixture closes
the leak on it.

**Spec sections exercised:**

- observability §8.4.3 — each `generation.usage` counter is omitted when its source counter is not
  reported; the Langfuse `Usage` record carries only the counters the provider reported.
- llm-provider §7 *Malformed usage counter* — a malformed counter is not reported (that counter is
  `null`); the others stand.

**Cases:**

1. `generation_usage_omits_input_when_prompt_tokens_null` — one LLM-calling node; Langfuse observer,
   `disable_provider_payload=False`. Mock usage `{null, 5, 15}`. Asserts `generation.usage` = `{output:
   5, total: 15}` — the `input` field omitted (the missing key is the omission, exact-map, as fixture 140
   asserts an empty `usageDetails`) — with the rest of the Generation (model, output, metadata, DEFAULT
   level) unaffected.

**What passes:**

- `generation.usage` carries `output` = 5 and `total` = 15 and **no** `input` field.
- Model, output, and metadata (`finish_reason`, `system`, `response_model`, `response_id`) emit
  unchanged.

**What fails:**

- `generation.usage.input` present (e.g. `0`, or `null`-typed) — a mapping that did not adopt the §8.4.3
  omit-on-not-reported guard.
- `output` or `total` dropped, or the observation misrendered.
