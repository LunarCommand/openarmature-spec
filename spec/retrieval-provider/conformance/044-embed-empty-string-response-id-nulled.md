# 044 — empty-string `response_id` is not present (nulled)

The sibling of 040's malformed-id case (a number where a string belongs) for the **empty-string** edge.
retrieval-provider §4 / §6 say `response_id` is "the provider-returned response identifier when present;
`null` otherwise," and proposal 0104 pins that an empty string `""` is **not** present — it is not a usable
identifier (correlates nothing, matches no provider record), so it is **absent**, not surfaced as
present-as-`""`.

**Why this diverges from 0097.** 0097 keeps an empty-string `document` echo **present** (`""`) because
`document` is **content** — an empty echo is a faithful reproduction of what the provider returned.
`response_id` is an **identifier** — an empty id carries no such signal; it is simply the absence of an id.
Content preserves the empty value; an identifier collapses it to absent. The rule is at the level of what the
field is *for*.

**Spec sections exercised:**

- retrieval-provider §4 — `EmbeddingResponse.response_id`: an empty-string identifier is not present → `null`;
  the empty value is not fabricated away — the verbatim `""` is preserved on `raw`.
- retrieval-provider §8.4 Cohere — `/v2/embed`: the top-level `id` maps to `response_id`; `embeddings.float`
  → vectors; `meta.billed_units.input_tokens` → usage (judged independently of the id).
- graph-engine §6 — the rule binds `EmbeddingEvent.response_id`: an empty id MUST NOT be surfaced on the event
  either (the observability spans / Langfuse observations render from the event).

**Case:**

1. `empty_string_response_id_nulled` — 2 inputs, one `/v2/embed` POST. The mocked response carries sound
   `embeddings.float` and a sound `input_tokens` (6), but the top-level `id` is `""`. `response_id` is `null`
   (not `""`); `usage` is unaffected; the verbatim `""` is preserved on `raw`; `EmbeddingEvent.response_id` is
   `null` to match.

**What passes:**

- `EmbeddingResponse.response_id` is `null`, and `EmbeddingEvent.response_id` is `null` — the empty id is
  absent on both the response and the typed event.
- `vectors` assemble from `embeddings.float` in input order; `usage.input_tokens` is `6` (the empty id does
  not affect the sound token count).
- `raw` preserves the verbatim `""` id.

**What fails:**

- Surfacing `""` on `response_id` or on `EmbeddingEvent.response_id` (treating an empty id as present).
- Raising `provider_invalid_response` over the empty id (it is an ancillary figure, not a payload defect).
- Fabricating the id away from `raw`, or letting the empty id null the sound `usage`.
