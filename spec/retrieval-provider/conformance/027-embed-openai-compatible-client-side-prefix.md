# 027 — OpenAI-compatible `/v1/embeddings` client-side prefix (asymmetric behind a compatible endpoint)

Verifies the retrieval-provider §8.3 client-side prefix fallback — the only way to express the
query/document distinction on the OpenAI `/v1/embeddings` wire, which has no `input_type` field. For an
**asymmetric** model served behind a compatible endpoint (e.g. a BGE / E5 model on vLLM), the mapping
reuses 0077 §8.1's optional `query_prefix` / `document_prefix`: when bound at construction, `input_type`
selects which prefix to **prepend client-side** to each input before sending. This is the §8.3
realization of 0077's client-side-prefix fallback, which no prior fixture exercised (013–017 use TEI's
server-side `prompt_name`; 020 uses Jina's `task`).

**Spec sections exercised:**

- retrieval-provider §2 — *Embedding runtime config* `input_type` (`"query"` / `"document"`).
- retrieval-provider §3 — `input_type` flows into `EmbeddingEvent.request_params` (graph-engine §6).
- retrieval-provider §8.3 OpenAI-compatible embeddings — *Construction*: MAY bind the optional
  client-side `query_prefix` / `document_prefix` from §8.1. *`input_type`*: for an asymmetric model
  behind a compatible endpoint, `input_type` selects the bound prefix, prepended client-side before
  sending — the only way to express the distinction on a wire with no `input_type` field.

**Cases:**

1. `input_type_query_prepends_query_prefix_client_side` — provider bound with `query_prefix: "query: "`
   / `document_prefix: "passage: "`. `embed(config={input_type: "query"})` MUST send wire
   `input: ["query: how tall is the eiffel tower?"]` (prefixed client-side), with NO `input_type` /
   `task` field on the wire and `Authorization: Bearer` present. `input_type` MUST reach
   `EmbeddingEvent.request_params` as `"query"` (the un-prefixed caller intent — the prefix is a wire
   detail).
2. `input_type_document_prepends_document_prefix_client_side` — same provider;
   `embed(config={input_type: "document"})` MUST send wire
   `input: ["passage: the eiffel tower is 330 metres tall."]`. No `input_type` / `task` field on the
   wire; `Authorization: Bearer` present; `EmbeddingEvent.request_params` carries `input_type: document`.

**What passes:**

- The wire `input` is the original text with `query_prefix` (for `"query"`) / `document_prefix` (for
  `"document"`) prepended; the wire still carries no `input_type` / `task` field (the distinction lives
  in the prefixed text).
- The `Authorization: Bearer` header is present; `input_type` reaches `EmbeddingEvent.request_params` as
  the un-prefixed value.

**What fails:**

- The prefix is not prepended (input sent verbatim despite a bound prefix), the wrong prefix is applied,
  or both inputs get the same prefix.
- An `input_type` / `task` field is injected onto the wire instead of (or in addition to) the prefix.
- The prefixed wire string leaks into `EmbeddingEvent.request_params` instead of the un-prefixed
  `input_type` value, or `input_type` is dropped from the event.
