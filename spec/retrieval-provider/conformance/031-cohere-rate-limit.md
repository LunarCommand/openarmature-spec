# 031 — Cohere HTTP 429 → `provider_rate_limit`

Locks the retrieval-provider §8.4 Cohere *Errors* mapping: a Cohere HTTP 429 (rate limit) MUST map to
`provider_rate_limit` (§7), NOT `provider_unavailable`. Parallel to the Jina `022` rate-limit fixture,
but single-case — the Cohere mapping is rerank-only (no `EmbeddingProvider` counterpart), so there is no
embedding surface to cover. The §7 category exception MUST raise out of the `rerank()` call — the adapter
MUST NOT loop or retry (a pipeline-utilities concern per §5 / §10).

**Spec sections exercised:**

- retrieval-provider §8.4 Cohere — *Errors*: `429` (rate limit) → `provider_rate_limit`.
- retrieval-provider §7 — `provider_rate_limit` category; the exception-flow contract (the category
  exception MUST raise out of `rerank()`).
- retrieval-provider §5 — `rerank()` MUST NOT loop, retry, or fall back.

**Cases:**

1. `rerank_429_maps_to_provider_rate_limit` — a `/v2/rerank` call where Cohere returns HTTP 429. The
   adapter MUST classify it as `provider_rate_limit` and raise out of the rerank node (not
   `provider_unavailable`, not a retry loop). The wire request carries the `Authorization: Bearer` header
   and the `{model, query, documents}` body.

**What passes:**

- The 429 maps to `provider_rate_limit`, raised out of the rerank node.
- The `Authorization: Bearer <api_key>` header is present on the request.

**What fails:**

- The 429 misclassified as `provider_unavailable` (the bug the §8.4 *Errors* enumeration pins) or any
  other §7 category.
- The adapter retries / loops on the 429 instead of raising.
