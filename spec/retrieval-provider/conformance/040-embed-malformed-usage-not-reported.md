# 040 — Cohere `/v2/embed` malformed ancillary figure is *not reported*

Verifies retrieval-provider §7 *Malformed ancillary figures* on the §8.4 Cohere **embedding** mapping: a
figure present on the wire but **malformed** in an ancillary field (the figures inside `usage`;
`response_id`) is treated as **not reported**. The call **succeeds** — no §7 category is raised, because the
vectors are sound and a garbage accounting figure says nothing about them — the figure is **nulled** (never
fabricated, coerced, clamped, or repaired), and the verbatim malformed value stays on `raw` (§4). Each
figure is judged **independently**, so the outcome follows §4's existing record rules: a malformed
`EmbeddingUsage.input_tokens` (a single-figure record) collapses `usage` to `null`, while a malformed
top-level `id` nulls `response_id`. The rule binds the **typed event** as well (graph-engine §6): a figure
not reported on the response is not surfaced on `EmbeddingEvent.usage` / `EmbeddingEvent.response_id`
either.

**Spec sections exercised:**

- retrieval-provider §7 *Malformed ancillary figures* — a malformed ancillary figure MUST NOT raise
  `provider_invalid_response` (or any §7 category); MUST NOT be fabricated, coerced, clamped, or repaired;
  MUST remain verbatim on `raw`; and is nulled per-figure per §4's record rules. The rule binds the typed
  `EmbeddingEvent` (graph-engine §6 — the observability spans / Langfuse observations render from the
  event, so a figure emitted there would reach the trace and billing surfaces regardless of the response).
- retrieval-provider §4 — `EmbeddingUsage` is present only when its figure is (single-figure collapse to
  `usage = null`); `response_id` is "the provider-returned identifier when present; null otherwise"; `raw`
  is the verbatim deserialized response.
- retrieval-provider §8.4 Cohere — the `/v2/embed` request/response mapping (unchanged from 032):
  `embeddings.float` → vectors in input order; `meta.billed_units.input_tokens` → `EmbeddingUsage.input_tokens`;
  top-level `id` → `response_id`; `model` is the bound id (Cohere echoes none).

The **payload** side is unchanged: §7's enumerated payload invariants and 0097's `document` rule stand
untouched; this fixture exercises only the ancillary carve-out.

**Cases:**

1. `malformed_input_tokens_collapses_usage_to_null` — 2 inputs, default config. The mocked Cohere response
   carries sound `embeddings.float` (two 4-d vectors) and a sound top-level `id`, but
   `meta.billed_units.input_tokens` is the string `"abc"`. `EmbeddingResponse.usage` collapses to `null`
   (single-figure record); vectors and `dimensions` intact; `response_id` surfaces normally (judged
   independently); no raise; the verbatim `"abc"` preserved on `raw`; `EmbeddingEvent.usage` is `null`.
2. `malformed_response_id_nulled` — 2 inputs, default config. The mocked response carries sound
   `embeddings.float` and a sound `meta.billed_units.input_tokens` (`6`), but the top-level `id` is the
   number `12345` (a number where a string id belongs). `EmbeddingResponse.response_id` is `null`; `usage`
   is `{input_tokens: 6}` (unaffected); no raise; the verbatim `12345` preserved on `raw`;
   `EmbeddingEvent.response_id` is `null`.

**What passes:**

- Exactly one `/v2/embed` request; the request wire shape unchanged from 032 (`model`, `input_type:
  "search_document"` default, `texts`, `embedding_types: ["float"]`, `truncate: "NONE"`, no `output_dimension`).
- Case A: `usage` is `null` (single-figure collapse), NOT `{input_tokens: 0}` and NOT `{input_tokens:
  "abc"}`; vectors / `dimensions` intact; `response_id` sound; `EmbeddingEvent.usage` `null`.
- Case B: `response_id` is `null`, NOT the stringified `"12345"`; `usage` unaffected (`{input_tokens: 6}`);
  `EmbeddingEvent.response_id` `null`.
- No `provider_invalid_response` (or any §7 category) is raised — the call completes and the state is
  populated.
- The verbatim malformed value (`"abc"` / `12345`) is preserved byte-for-value on `raw`.

**What fails:**

- Raising `provider_invalid_response` over the malformed accounting figure (discarding a sound result).
- Coercing / repairing the figure — parsing `"abc"`, fabricating a `0`, or stringifying `12345` to
  `"12345"` (a repaired figure is indistinguishable from a reported one).
- Surfacing the malformed figure on `EmbeddingEvent.usage` / `EmbeddingEvent.response_id` while the response
  reports it as absent (the corrupt value would reach the span / trace / billing surfaces anyway).
- Dropping the verbatim malformed value from `raw`, or letting the malformed ancillary figure disturb the
  vectors / `dimensions` / the sound sibling figure.
