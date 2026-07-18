# 149 — Malformed wire counter nulled through the mapping to the event and span

Verifies the **malformed → null → event/span seam** (proposal 0101) end-to-end, driven from a genuinely
**malformed wire counter**. Fixtures 144–148 mock a counter that is *already* `null` on the wire (the
post-nulling state) and assert the observability rendering of a null counter; they do **not** drive a
malformed wire value through the provider mapping. This fixture closes that gap: it mocks a malformed
counter on the wire (`"abc"`, `-5`, `true`) and asserts it is nulled by the real `complete()` mapping
(llm-provider §7 *Malformed usage counter*) **before** the typed `LlmCompletionEvent` and the OTel span
render it.

**Why this is expressible obs-side.** `calls_llm` issues a **real `complete()` call against the mock
provider** (conformance-adapter §5.1 / §5.5); the `mock_llm` `body` is an OpenAI-compatible
chat-completion **wire** shape (llm-provider §8) that the real provider mapping parses. So a malformed
wire counter flows through the same malformed → `null` path the sibling llm-provider fixtures (068–071)
test in isolation, then out to `LlmCompletionEvent.usage` (the graph-engine §6 mirror 0101 pins as
load-bearing) and the §5.5.3 span attributes.

**The discriminator.** An implementation that nulls `Response.usage` but sources
`LlmCompletionEvent.usage` from `raw` (which carries `"abc"` / `-5` / `true` verbatim) surfaces the
malformed value on the event and **fails** `contains_event` here — the exact bypass 144–148 cannot catch,
because they mock the post-nulling `null` (a raw-sourced event would coincidentally read `null` too).

**Spec sections exercised:**

- llm-provider §7 *Malformed usage counter* — a malformed wire counter is not reported (that counter is
  `null`); the sound counters stand. Exercised through the real `complete()` mapping, not mocked
  post-nulling.
- graph-engine §6 — `LlmCompletionEvent.usage` mirrors `Response.usage`: a present record with the
  malformed counter(s) `null` (partial), or a present record of null counters (all-malformed) — never a
  null `usage` and never the verbatim wire value.
- observability §5.5.3 — `gen_ai.usage.input_tokens` / `openarmature.llm.usage.prompt_tokens` (and, in the
  all-malformed case, every usage attribute) omitted per-field when their counter is not reported; the
  sound counters emit.

**Cases:**

1. `malformed_wire_prompt_tokens_nulled_through_mapping_to_event_and_span` — wire usage
   `{prompt_tokens: "abc", completion_tokens: 5, total_tokens: 15}`. Asserts `LlmCompletionEvent.usage` is
   `{prompt_tokens: null, completion_tokens: 5, total_tokens: 15}` (the wire `"abc"` is **not** present),
   and the span omits `gen_ai.usage.input_tokens` and `openarmature.llm.usage.prompt_tokens` while emitting
   the sound output pair and the total.
2. `all_three_malformed_wire_counters_surface_as_present_record_of_nulls_on_event` — wire usage
   `{prompt_tokens: "abc", completion_tokens: -5, total_tokens: true}`. Asserts `LlmCompletionEvent.usage`
   is a **present record of** `{null, null, null}` (§6 null-together) — **not** a null `usage` — and the
   span omits every usage attribute.

**What passes:**

- Case 1 — the event carries `prompt_tokens: null` (not `"abc"`), `completion_tokens: 5`,
  `total_tokens: 15`; the span omits both input attributes and emits `gen_ai.usage.output_tokens` = 5,
  `openarmature.llm.usage.completion_tokens` = 5, `openarmature.llm.usage.total_tokens` = 15, plus identity.
- Case 2 — the event carries a present record of three `null` counters; the span omits all five usage
  attributes; identity attributes emit unchanged.

**What fails:**

- **The discriminator:** the event carries the verbatim wire value (`"abc"` / `-5` / `true`) on any
  counter — an impl sourcing `LlmCompletionEvent.usage` from `raw` rather than mirroring the nulled
  `Response.usage`.
- Case 2 — the event surfaces a **null** `usage` record instead of a present record of null counters.
- The span emits `gen_ai.usage.input_tokens` (or its mirror) sourced from a nulled counter.
- The implementation raises `provider_invalid_response` over the malformed wire counter, so no completion
  event / span is produced.
