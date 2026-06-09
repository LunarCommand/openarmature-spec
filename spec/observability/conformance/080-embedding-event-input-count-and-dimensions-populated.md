# 080 — `EmbeddingEvent.input_count` and `dimensions` convenience fields populated

Verifies graph-engine §6's convenience-field population on `EmbeddingEvent` (per proposal
0059). The `input_count` field equals the input list length; the `dimensions` field equals
the inner-vector length from the response. Both are derivable from other fields but kept on
the event for cross-vendor ergonomics.

**Spec sections exercised:**

- graph-engine §6 — `EmbeddingEvent.input_count` and `dimensions` convenience fields.

**Cases:**

1. `input_count_and_dimensions_populated_from_call` — `embed()` called with 4 input strings;
   provider returns 4 vectors of dimension 5. Asserts `input_count=4` and `dimensions=5` on
   the typed event.

**What passes:**

- Both convenience fields populated with the expected values.

**What fails:**

- Either field is null — the adapter did not populate the convenience field.
- The values disagree with the input list length / response inner-vector length — the adapter
  computed them incorrectly.
