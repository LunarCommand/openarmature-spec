# 020 — Jina `/v1/embeddings` `input_type` → `task` realization

Verifies the retrieval-provider §8.2 Jina embedding mapping's `input_type` realization plus the §2 /
§3 `input_type` protocol contract — the cross-vendor payoff: the same `EmbeddingRuntimeConfig.input_type`
knob (placed on the protocol by 0077) realized on a **second** wire, Jina's native `task`, after TEI's
`prompt_name` (fixture 013). A Jina `EmbeddingProvider` MUST translate the caller's `input_type` into
Jina's `task` field per the §8.2 closed set (`query → retrieval.query`, `document → retrieval.passage`),
and MUST flow `input_type` into `EmbeddingEvent.request_params` with absence-is-meaningful semantics.

**Spec sections exercised:**

- retrieval-provider §2 — *Embedding runtime config* `input_type` (`"query"` / `"document"`; absent ⇒
  symmetric) and `dimensions`.
- retrieval-provider §3 — `input_type` flows into `EmbeddingEvent.request_params` (graph-engine §6)
  with the same absence-is-meaningful semantics as `dimensions`.
- retrieval-provider §8.2 Jina — *Construction*: API key sent as `Authorization: Bearer <key>`.
  `/v1/embeddings` request `{model, input, task?, dimensions?, truncate: false}`; `input_type`
  realization sets `task` from the closed set `query → retrieval.query` / `document → retrieval.passage`;
  `input_type` absent ⇒ `task` omitted; `dimensions` → Jina's `dimensions`; the response
  `{model, usage, data: [{index, embedding}]}` maps to vectors in input order.

**Cases:**

1. `input_type_query_sends_task_retrieval_query` — `embed(config={input_type: "query"})`. The
   `/v1/embeddings` wire request MUST carry `task: "retrieval.query"` alongside `{model, input,
   truncate: false}`; `EmbeddingEvent.request_params` MUST carry `input_type: query`.
2. `input_type_document_sends_task_retrieval_passage` — `embed(config={input_type: "document"})` ⇒
   `task: "retrieval.passage"`; the event MUST carry `input_type: document`.
3. `input_type_absent_omits_task_symmetric_default` — `embed()` with no config. The wire request MUST
   NOT carry `task` (the symmetric / model default); the body is exactly `{model, input, truncate:
   false}`. `EmbeddingEvent.request_params` MUST be the empty mapping (no `input_type` key).
4. `dimensions_maps_to_jina_dimensions_field` — `config={dimensions: 4}` ⇒ the wire request carries
   Jina's `dimensions` field; `task` stays ABSENT (no `input_type`).

**What passes:**

- The wire request carries the mapped `task` for `"query"` / `"document"` and omits it when `input_type`
  is absent; `dimensions` appears on the wire only when supplied.
- `model` and `truncate: false` are on every request; the `Authorization: Bearer <api_key>` header is
  present.
- `input_type` reaches `EmbeddingEvent.request_params` when supplied; the mapping is empty when absent.

**What fails:**

- The mapping sends the literal `input_type` string (e.g. `"query"`) instead of the mapped `task`
  (`"retrieval.query"`).
- A `task` is emitted when `input_type` is absent — the symmetric default is broken.
- `dimensions` emitted when not supplied, or `truncate` / `model` omitted.
- The `Authorization: Bearer` header missing.
- `input_type` dropped from `EmbeddingEvent.request_params`, or a key appears when none was supplied
  (absence-is-meaningful violated).
