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
- retrieval-provider §6 — `ScoredDocument.document` surfaces the provider's echoed **text**: a string
  echo verbatim (an empty string is *present* → `""`, not folded to null), a text-bearing object
  (`{"text": str}`) unwrapped to its text, any other object (no string `text`) → null, absent/`null` →
  null; the mapping MUST NOT fabricate the echo from the input `documents` list. Per-result shape
  variance is honored. The verbatim echo object is preserved on `RerankResponse.raw`.
- retrieval-provider §8.2 Jina — `/v1/rerank` `return_documents` ← `RerankRuntimeConfig.return_documents`,
  **sent explicitly** (Jina's wire default is `true`, OA's is `False`). Jina's rerank `document` is
  `anyOf[string, TextDoc, ImageDoc, null]` (`TextDoc = {"text": str}`, `ImageDoc = {"image": str}`);
  a string → itself, a `TextDoc` → its `text`, an `ImageDoc` (or any object without a string `text`) →
  null, absent/`null` → null, with the verbatim echo preserved on `raw`.

**Cases:**

1. `return_documents_default_false_overrides_jina_wire_default` — 3 documents, default config (no
   `return_documents` field ⇒ OA default `False`). The wire request MUST carry `return_documents:
   false` explicitly (overriding Jina's `true` wire default). The mocked response omits `document` on
   each result, so every `ScoredDocument.document` MUST be null. Response UNSORTED ⇒ sorted descending.
2. `return_documents_true_populates_document_echo` — `config={return_documents: True}` ⇒ the wire
   request carries `return_documents: true`; the Jina-echoed `document` per result (a **string**) MUST
   surface verbatim on `ScoredDocument.document`. Response again UNSORTED.
3. `document_echo_textdoc_object_unwraps_to_text` — Jina echoes each `document` as a **TextDoc object**
   (`{"text": str}`, the shape the text reranker typically returns). Per §6 / §8.2 the mapping
   unwraps the object to its `text` string on `ScoredDocument.document` (not the object), while the
   verbatim TextDoc object is preserved on `RerankResponse.raw`. Response UNSORTED.
4. `document_echo_imagedoc_object_maps_to_null` — Jina echoes each `document` as an **ImageDoc object**
   (`{"image": str}`), a documented member shape with no string `text`. Per §6 / §8.2 the mapping
   surfaces `null` on `ScoredDocument.document` (no text to surface; the documented shape is **not**
   malformed), and the verbatim ImageDoc object is preserved on `RerankResponse.raw` so the non-text
   (image) echo remains recoverable. Response UNSORTED.
5. `document_echo_mixed_shapes_per_result` — one response whose 4 results echo **different shapes**:
   index 0 a bare string, index 1 a TextDoc, index 2 an ImageDoc, index 3 absent. Exercising §6's
   per-result shape variance, each surfaces per the §8.2 rule (string → itself, TextDoc → its text,
   ImageDoc → null, absent → null) carried to its sorted position; the verbatim mixed-shape echoes are
   preserved on `RerankResponse.raw` in provider order. Distinct scores make the sort deterministic
   (idx1 > idx3 > idx0 > idx2).
6. `document_echo_empty_string_present_distinct_from_absent` — one result echoes an **empty string**
   (`document: ""`), the other **omits** `document`. Per §6 the empty string is *present* and surfaces
   as `""` (**not** folded to null), while the absent echo surfaces null — pinning the present-vs-absent
   distinction the object-shape cases don't reach. The verbatim response is preserved on
   `RerankResponse.raw`.

**What passes:**

- The default case sends `return_documents: false` on the wire (not relying on Jina's `true` default);
  the `True` case sends `return_documents: true`.
- The `Authorization: Bearer <api_key>` header is present on both requests.
- `document` is null when Jina omits the echo (default case) and equals the provider echo verbatim
  when Jina returns a string (`True` case).
- A TextDoc object echo (`{"text": str}`) surfaces its `text` string on `ScoredDocument.document`
  (case C); an ImageDoc object echo (`{"image": str}`) surfaces `null` (case D); a response mixing
  string / TextDoc / ImageDoc / absent echoes surfaces each per the §8.2 rule at its sorted position
  (case E).
- The verbatim provider response — including the object echoes nested in `results[].document` — is
  preserved on `RerankResponse.raw` (cases C, D, E), so a non-text (image) echo remains recoverable.
- An empty-string echo (`document: ""`) surfaces as `""` (present), distinct from an absent echo which
  surfaces null (case F).
- Results sorted descending; each `index` valid into the input documents.

**What fails:**

- The default case omits `return_documents` (relying on Jina's `true` default would silently diverge
  from OA's `False`), or sends `true`.
- `document` auto-filled from the input `documents` list when Jina omitted the echo, or dropped when
  Jina echoed it.
- The echo populated for the default-`False` case (Jina echoes nothing when `return_documents` is
  false).
- A TextDoc object surfaced raw as the object (not unwrapped to its `text`), or an ImageDoc / other
  text-less object surfaced as anything but `null` — or either documented shape rejected as malformed.
- The object echo dropped from `RerankResponse.raw` (raw must preserve the verbatim response, including
  the nested `document` objects), or `raw` reshaped to the sorted/normalized `results`.
- An empty-string echo (`document: ""`) folded to null instead of surfacing as `""` (case F).
