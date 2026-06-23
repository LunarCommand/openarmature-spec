# 019 — Jina `/v1/rerank` `return_documents` honors the OA default

Verifies the headline behavior the retrieval-provider §8.2 accept fixes: Jina's wire
`return_documents` defaults `true`, but OA's `RerankRuntimeConfig.return_documents` defaults `False`
(§2 / §6), so the Jina mapping MUST send `return_documents` **explicitly** rather than relying on
Jina's wire default. The default-`False` case sends `return_documents: false` (overriding Jina's
`true`); the `True` case sends `return_documents: true` and surfaces the Jina-echoed `document`
verbatim on `ScoredDocument.document`.

**Spec sections exercised:**

- retrieval-provider §2 — *Rerank runtime config*: `return_documents` boolean, default `False`; the
  §8.2 Jina mapping sends the OA value explicitly because Jina's wire default is `True`.
- retrieval-provider §6 — `ScoredDocument.document` carries the provider's echo verbatim when present,
  null otherwise; the mapping MUST NOT fabricate the echo from the input `documents` list.
- retrieval-provider §8.2 Jina — `/v1/rerank` `return_documents` ← `RerankRuntimeConfig.return_documents`,
  **sent explicitly** (Jina's wire default is `true`, OA's is `False`).

**Cases:**

1. `return_documents_default_false_overrides_jina_wire_default` — 3 documents, default config (no
   `return_documents` field ⇒ OA default `False`). The wire request MUST carry `return_documents:
   false` explicitly (overriding Jina's `true` wire default). The mocked response omits `document` on
   each result, so every `ScoredDocument.document` MUST be null. Response UNSORTED ⇒ sorted descending.
2. `return_documents_true_populates_document_echo` — `config={return_documents: True}` ⇒ the wire
   request carries `return_documents: true`; the Jina-echoed `document` per result MUST surface
   verbatim on `ScoredDocument.document`. Response again UNSORTED.

**What passes:**

- The default case sends `return_documents: false` on the wire (not relying on Jina's `true` default);
  the `True` case sends `return_documents: true`.
- The `Authorization: Bearer <api_key>` header is present on both requests.
- `document` is null when Jina omits the echo (default case) and equals the provider echo verbatim
  when Jina returns it (`True` case).
- Results sorted descending; each `index` valid into the input documents.

**What fails:**

- The default case omits `return_documents` (relying on Jina's `true` default would silently diverge
  from OA's `False`), or sends `true`.
- `document` auto-filled from the input `documents` list when Jina omitted the echo, or dropped when
  Jina echoed it.
- The echo populated for the default-`False` case (Jina echoes nothing when `return_documents` is
  false).
