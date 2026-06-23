# 021 — Jina `/v1/rerank` `truncation: false` fail-loud

Verifies the retrieval-provider §8.2 Jina *`truncation` / `truncate` (fail-loud)* contract on the
rerank endpoint. Jina names the flag `truncation` on `/v1/rerank`; the mapping sends `truncation:
false` explicitly, so an over-length `(query, document)` pair makes Jina error (HTTP 422) rather than
silently truncating. The resulting error MUST map to `provider_invalid_request` (§7) and raise out of
the rerank call — the adapter MUST NOT return a silently truncated score.

(Jina names the flag `truncate` on `/v1/embeddings`; its fail-loud value `false` is asserted on every
`/v1/embeddings` request in fixture 020. This fixture covers the `/v1/rerank` `truncation` surface,
where a truncated pair would yield a wrong relevance score.)

**Spec sections exercised:**

- retrieval-provider §8.2 Jina — *`truncation` / `truncate` (fail-loud)*: the per-endpoint flag is
  sent `false` so an over-length input errors; *Errors*: over-length / malformed request (`422`) →
  `provider_invalid_request`.
- retrieval-provider §7 — `provider_invalid_request` category; the exception-flow contract (the
  category exception MUST raise out of `rerank()`).

**Cases:**

1. `over_length_422_maps_to_provider_invalid_request` — an over-length pair; Jina returns HTTP 422. The
   adapter MUST classify it as `provider_invalid_request` and raise out of the rerank node. The wire
   request still carries `truncation: false` and the `Authorization: Bearer` header.

**What passes:**

- The wire request carries `truncation: false` and the `Authorization: Bearer <api_key>` header.
- The 422 over-length response maps to `provider_invalid_request`, raised out of the rerank node.

**What fails:**

- `truncation` omitted or sent `true` (would let Jina silently truncate).
- A different §7 category is raised (e.g. `provider_unavailable`), or no exception is raised and a
  truncated score is returned.
