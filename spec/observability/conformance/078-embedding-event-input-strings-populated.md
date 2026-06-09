# 078 — `EmbeddingEvent.input_strings` populated verbatim

Verifies graph-engine §6's `input_strings` field population on `EmbeddingEvent` (per proposal
0059). The field MUST carry the input list verbatim from the `embed()` call site. Mirrors
fixture 060 for the LLM-side variant's `input_messages` field.

**Spec sections exercised:**

- graph-engine §6 — `EmbeddingEvent.input_strings` population (always populated; observer-side
  privacy gating at the rendering boundary per observability §5.5.4).

**Cases:**

1. `input_strings_populated_verbatim` — `embed()` called with a 3-element input list. Asserts
   the typed event's `input_strings` field carries the input list element-for-element.

**What passes:**

- `input_strings` matches the input list exactly.

**What fails:**

- `input_strings` is empty or null — the adapter did not populate the field on the typed event
  (the rendering-boundary privacy posture applies at the observer, not at the field-population
  layer).
- The list is permuted or partial — the dispatch path mutated the field.
