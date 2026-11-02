# 031 — Cohere HTTP 429 → `provider_rate_limit`

Locks the retrieval-provider §8.4 Cohere *Errors* mapping: a Cohere HTTP 429 (rate limit) MUST map to
`provider_rate_limit` (§7), NOT `provider_unavailable`. Like the Jina `022` rate-limit fixture, it covers
both Cohere endpoints, rerank and embed, which §8.4 maps alike. In both, the §7 category exception MUST
raise out of the call, and the adapter MUST NOT loop or retry (a pipeline-utilities concern per §3, §5
and §10).

**Spec sections exercised:**

- retrieval-provider §8.4 Cohere *Errors*: `429` (rate limit) → `provider_rate_limit`.
- retrieval-provider §7: the `provider_rate_limit` category, and the exception-flow contract (the
  category exception MUST raise out of `rerank()` and `embed()`).
- retrieval-provider §3 and §5: `embed()` and `rerank()` MUST NOT loop, retry, or fall back.

**Cases:**

1. `rerank_429_maps_to_provider_rate_limit`: a `/v2/rerank` call where Cohere returns HTTP 429. The
   adapter MUST classify it as `provider_rate_limit` and raise out of the rerank node (not
   `provider_unavailable`, not a retry loop). The wire request carries the `Authorization: Bearer` header
   and the `{model, query, documents}` body.
2. `embed_429_maps_to_provider_rate_limit`: a `/v2/embed` call where Cohere returns HTTP 429. The adapter
   MUST classify it as `provider_rate_limit` and raise out of the embed node. Exactly one wire request is
   sent, carrying the `Authorization: Bearer` header and the `/v2/embed` body, with the mandatory
   `input_type` defaulted to `search_document` (§8.4).

**What passes:**

- The 429 maps to `provider_rate_limit`, raised out of the calling node, on both endpoints.
- The `Authorization: Bearer <api_key>` header is present on the request.

**What fails:**

- The 429 misclassified as `provider_unavailable` (the bug the §8.4 *Errors* enumeration pins) or any
  other §7 category, on either endpoint.
- The adapter retries / loops on the 429 instead of raising.
