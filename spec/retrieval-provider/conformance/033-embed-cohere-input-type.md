# 033 — Cohere `/v2/embed` `input_type` → wire `input_type` (incl. the mandatory default)

Verifies the retrieval-provider §8.4 Cohere embedding mapping's `input_type` realization plus the §2 / §3
`input_type` protocol contract — the **third** realization of 0077's `input_type` knob (after TEI's
`prompt_name`, fixture 013, and Jina's `task`, fixture 020) and the **first where the wire field is
mandatory**. Cohere v2 `/v2/embed` requires `input_type` on every request, so this mapping is the one that
must define what the **absent** OA value maps to: it cannot omit the field.

**Spec sections exercised:**

- retrieval-provider §2 — *Embedding runtime config* `input_type` (`"query"` / `"document"`; the closed
  set §8.4 recognizes).
- retrieval-provider §3 — `input_type` flows into `EmbeddingEvent.request_params` (graph-engine §6) with
  absence-is-meaningful semantics.
- retrieval-provider §8.4 Cohere — *`input_type` (mandatory wire field)*: the mapping MUST always send a
  value; `query → search_query`, `document → search_document`, and **absent ⇒ `search_document`** (the
  bulk-indexing default — the wire requires a value). An unrecognized OA `input_type` is a pre-send
  `provider_invalid_request` (fixture 034).

**Cases:**

1. `input_type_query_sends_search_query` — `embed(config={input_type: "query"})`. The `/v2/embed` wire
   request MUST carry `input_type: "search_query"`; `EmbeddingEvent.request_params` MUST carry
   `input_type: query`.
2. `input_type_document_sends_search_document` — `embed(config={input_type: "document"})` ⇒
   `input_type: "search_document"`; the event MUST carry `input_type: document`.
3. `input_type_absent_sends_search_document_mandatory_default` — `embed()` with no config. The wire request
   MUST carry `input_type: "search_document"` (the mandatory-field default — the case no other embed
   mapping has, since §8.1 / §8.2 omit the field when absent and §8.3 has none). Per
   absence-is-meaningful, `EmbeddingEvent.request_params` MUST be the **empty** mapping (no `input_type`
   key) **even though** the wire carries `search_document` — the wire default MUST NOT be reflected back
   onto the event as if the caller set it.

**What passes:**

- The wire request carries the mapped `input_type` (`search_query` for `query`, `search_document` for
  `document`, and `search_document` when the OA `input_type` is absent); `embedding_types: ["float"]` and
  `truncate: "NONE"` on every request; the `Authorization: Bearer <api_key>` header present.
- `input_type` reaches `EmbeddingEvent.request_params` when supplied; the mapping is empty when absent
  (the wire's mandatory `search_document` default does not leak onto the event).

**What fails:**

- The mapping sends the literal OA `input_type` string (e.g. `"query"`) instead of the mapped wire value
  (`"search_query"`).
- The wire omits `input_type` (Cohere requires it), or the absent-OA case sends anything other than
  `search_document`.
- The absent-OA case populates `EmbeddingEvent.request_params` with `input_type: document` (reflecting the
  wire default back onto the event — absence-is-meaningful violated), or a supplied `input_type` is dropped
  from the event.
- `embedding_types` / `truncate` omitted, or the `Authorization: Bearer` header missing.
