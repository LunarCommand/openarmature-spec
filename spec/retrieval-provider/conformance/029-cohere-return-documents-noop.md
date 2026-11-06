# 029 — Cohere `/v2/rerank` `return_documents` is a no-op

Verifies the retrieval-provider §8.4 Cohere mapping's handling of `return_documents` — the rerank
negative-space companion to fixture 026 (0079's "`input_type` is a no-op on the symmetric OpenAI wire").
The Cohere `/v2/rerank` wire has **no** `return_documents` parameter and never echoes document text, so
OA's `RerankRuntimeConfig.return_documents` (§2) is **not realized** on the wire: the mapping adds no wire
field, leaves every `ScoredDocument.document` null regardless of the config value, and does not error.
Contrast Jina §8.2 (fixture 019), where `return_documents` *is* realized and the `true` case surfaces the
provider echo verbatim.

**Spec sections exercised:**

- retrieval-provider §2 *Rerank runtime config*: `return_documents` boolean, default `false`.
- retrieval-provider §6 — `ScoredDocument.document` is null when the provider omits the echo; the mapping
  MUST NOT fabricate it from the input `documents` list.
- retrieval-provider §8.4 Cohere — *`return_documents` (not realized — a silent no-op)*: the wire has no
  `return_documents` parameter and never echoes document text, so the knob is not realized, `document`
  stays null regardless of the config value, and the mapping does not error.

**Cases:**

1. `return_documents_true_is_noop_on_wire`: 3 documents with `config: {return_documents: true}`. The wire
   request MUST NOT carry a `return_documents` field; the body is exactly `{model, query, documents}` —
   byte-identical to the no-config request (case 2). The mapping MUST NOT error. The mocked response
   echoes no `document`, so every `ScoredDocument.document` MUST be null even though `return_documents: true`
   was requested. Response UNSORTED ⇒ sorted descending.
2. `return_documents_absent_same_body` — same 3 documents with no config (`return_documents` absent ⇒ OA
   default `false`). The wire body MUST be exactly `{model, query, documents}`: the byte-identical
   baseline case 1 is compared against (proving `return_documents` is a true wire no-op). Every
   `ScoredDocument.document` is null. Response again UNSORTED.

**What passes:**

- Both requests carry the same `{model, query, documents}` body with no `return_documents` field
  (byte-identical); the mapping does not error on `return_documents: true`.
- The `Authorization: Bearer <api_key>` header is present on both requests.
- Every `ScoredDocument.document` is null in both cases (Cohere echoes none), with no echo fabricated from
  the input `documents` list.
- Results sorted descending; each `index` valid into the input documents.

**What fails:**

- The `true` case injects a `return_documents` field onto the wire, or its body differs from the
  no-config body (the no-op is broken).
- The mapping errors on `return_documents: true` (it is a silent no-op, not an error).
- A `document` auto-filled from the input `documents` list when Cohere omitted the echo.
