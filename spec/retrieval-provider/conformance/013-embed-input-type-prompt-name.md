# 013 — TEI `/embed` `input_type` → `prompt_name` realization

Verifies the retrieval-provider §8.1 TEI embedding mapping's `input_type` realization plus the §2 /
§3 `input_type` protocol contract. A TEI `EmbeddingProvider` constructed with an
`input_type → prompt_name` map MUST translate the caller's `input_type` into TEI's native
`prompt_name` wire field (server-side prompts), and MUST flow `input_type` into
`EmbeddingEvent.request_params` with absence-is-meaningful semantics.

**Spec sections exercised:**

- retrieval-provider §2 — *Embedding runtime config* `input_type` (`"query"` / `"document"`,
  extensible; absent ⇒ symmetric).
- retrieval-provider §3 — `input_type` flows into `EmbeddingEvent.request_params` (graph-engine §6)
  with the same absence-is-meaningful semantics as `dimensions`.
- retrieval-provider §8.1 TEI — `/embed` `input_type` realization via TEI's native `prompt_name`
  looked up from the construction `input_type → prompt_name` map; `input_type` absent ⇒ no
  `prompt_name` (the symmetric default).
- graph-engine §6 — `EmbeddingEvent.request_params` carries the embedding-specific runtime-config
  fields the caller supplied.

**Cases:**

1. `input_type_query_sends_prompt_name_query` — `embed(config={input_type: "query"})` against a
   provider whose map binds `query → "query"`. The `/embed` wire request MUST carry
   `prompt_name: "query"`; `EmbeddingEvent.request_params` MUST carry `input_type: query`.
2. `input_type_document_sends_prompt_name_passage` — `embed(config={input_type: "document"})`;
   `document → "passage"` per the map, so the wire request MUST carry `prompt_name: "passage"` and the
   event MUST carry `input_type: document`.
3. `input_type_absent_omits_prompt_name_symmetric_default` — `embed()` with no config. The wire
   request MUST NOT carry `prompt_name` (the symmetric / pre-0077 path) and MUST be byte-identical to
   the symmetric `{"inputs": [...]}` body. `EmbeddingEvent.request_params` MUST be the empty mapping
   (no `input_type` key).

**What passes:**

- The wire request carries the mapped `prompt_name` for `"query"` / `"document"` and omits it when
  `input_type` is absent.
- The absent-`input_type` body is byte-identical to the symmetric path.
- `input_type` reaches `EmbeddingEvent.request_params` when supplied; the mapping is empty when absent.

**What fails:**

- The mapping sends the literal `input_type` string instead of the looked-up `prompt_name`.
- A `prompt_name` is emitted when `input_type` is absent — the symmetric default is broken.
- `input_type` is dropped from `EmbeddingEvent.request_params`, or a key appears when none was
  supplied (absence-is-meaningful violated).
