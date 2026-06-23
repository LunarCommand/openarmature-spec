# 026 — OpenAI-compatible `/v1/embeddings` `input_type` is a no-op (symmetric)

Verifies the retrieval-provider §8.3 OpenAI-compatible mapping's handling of `input_type` on the
**symmetric** base wire — 0077's "absent ⇒ symmetric" graceful degradation, exercised on a symmetric
mapping. Where TEI realizes `input_type` as `prompt_name` (013) and Jina as `task` (020), the OpenAI
`/v1/embeddings` wire has **no** query/document parameter, so the mapping does **not** realize
`input_type` on the wire — yet `input_type` still flows into `EmbeddingEvent.request_params` (§3). Both
halves are asserted.

**Spec sections exercised:**

- retrieval-provider §2 — *Embedding runtime config* `input_type` (`"query"` / `"document"`; absent ⇒
  symmetric).
- retrieval-provider §3 — `input_type` flows into `EmbeddingEvent.request_params` (graph-engine §6) with
  the same absence-is-meaningful semantics as `dimensions`.
- retrieval-provider §8.3 OpenAI-compatible embeddings — *`input_type`*: the wire has no query/document
  parameter, so on the base wire `input_type` is **not realized** — an absent `input_type` is the
  correct symmetric default for OpenAI's symmetric models, and the mapping does not error on it.

**Cases:**

1. `input_type_query_is_noop_on_symmetric_wire` — `embed(config={input_type: "query"})` against a
   symmetric provider (no `query_prefix` / `document_prefix` bound). The wire request MUST NOT carry any
   query/document/`input_type`/`task` field and MUST send `input` **verbatim** (un-prefixed); the body
   is exactly `{model, input}`, byte-identical to the no-`input_type` request (case 2). The mapping MUST
   NOT error. `input_type` MUST still reach `EmbeddingEvent.request_params` as `"query"`.
2. `input_type_absent_same_body` — `embed()` with no config, **same** input string. The wire body MUST
   be exactly `{model, input}` — the byte-identical baseline case 1 is compared against (proving
   `input_type` is a true wire no-op). `EmbeddingEvent.request_params` MUST be the empty mapping (no
   `input_type` key).

**What passes:**

- The `input_type: "query"` wire body carries no `input_type`/`task`/query/document field, sends `input`
  verbatim, and is byte-identical to the no-`input_type` body; the mapping does not error.
- `input_type` reaches `EmbeddingEvent.request_params` when supplied (even though the wire ignores it),
  and the mapping is empty when absent (absence-is-meaningful).

**What fails:**

- The mapping injects an `input_type` / `task` / query/document field onto the wire, prefixes `input`
  when no prefix is bound, or errors on `input_type` on a symmetric provider.
- The with-`input_type` body differs from the no-`input_type` body (the no-op is broken).
- `input_type` is dropped from `EmbeddingEvent.request_params`, or a key appears when none was supplied.
