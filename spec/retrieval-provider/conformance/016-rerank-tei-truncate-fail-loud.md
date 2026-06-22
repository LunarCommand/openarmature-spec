# 016 — TEI `/rerank` `truncate: false` fail-loud

Verifies the retrieval-provider §8.1 TEI `truncate: false (fail-loud)` contract. The mapping sends
`truncate: false` explicitly, so an over-length `(query, document)` pair makes TEI error (HTTP 413 /
422) rather than silently truncating. The resulting error MUST map to `provider_invalid_request`
(§7) and raise out of the rerank call — the adapter MUST NOT return a silently truncated score.

**Spec sections exercised:**

- retrieval-provider §8.1 TEI — *`truncate: false` (fail-loud)*: an over-length input errors;
  *Errors*: over-length / malformed request (413 / 422) → `provider_invalid_request`.
- retrieval-provider §7 — `provider_invalid_request` category; the exception-flow contract (the
  category exception MUST raise out of `rerank()`).

**Cases:**

1. `over_length_413_maps_to_provider_invalid_request` — an over-length pair; TEI returns HTTP 413.
   The adapter MUST classify it as `provider_invalid_request` and raise out of the rerank node. The
   wire request still carries `truncate: false`.
2. `over_length_422_maps_to_provider_invalid_request` — the same contract via HTTP 422 (the other
   over-length status TEI surfaces).

**What passes:**

- The wire request carries `truncate: false`.
- Both 413 and 422 over-length responses map to `provider_invalid_request`, raised out of the rerank
  node.

**What fails:**

- `truncate` omitted or sent `true` (would let TEI silently truncate).
- A different §7 category is raised (e.g. `provider_unavailable`), or no exception is raised and a
  truncated score is returned.
