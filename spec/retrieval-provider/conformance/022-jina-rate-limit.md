# 022 — Jina HTTP 429 → `provider_rate_limit`

Locks the retrieval-provider §8.2 Jina *Errors* mapping the accept fixes: a Jina HTTP 429 (rate limit)
MUST map to `provider_rate_limit` (§7), NOT `provider_unavailable`. Covered on both Jina endpoints
(`/v1/rerank` and `/v1/embeddings`) so the rate-limit classification holds across the rerank and
embedding surfaces. In both cases the §7 category exception MUST raise out of the call — the adapter
MUST NOT loop or retry (a pipeline-utilities concern per §5 / §10).

**Spec sections exercised:**

- retrieval-provider §8.2 Jina — *Errors*: `429` (rate limit) → `provider_rate_limit`.
- retrieval-provider §7 — `provider_rate_limit` category; the exception-flow contract (the category
  exception MUST raise out of `rerank()` / `embed()`).
- retrieval-provider §5 — `rerank()` (and §3 `embed()`) MUST NOT loop, retry, or fall back.

**Cases:**

1. `rerank_429_maps_to_provider_rate_limit` — a `/v1/rerank` call where Jina returns HTTP 429. The
   adapter MUST classify it as `provider_rate_limit` and raise out of the rerank node (not
   `provider_unavailable`, not a retry loop). The wire request carries the `Authorization: Bearer`
   header.
2. `embeddings_429_maps_to_provider_rate_limit` — an `/v1/embeddings` call where Jina returns HTTP 429,
   classified as `provider_rate_limit` and raised out of the embed node — locking the mapping on the
   embedding surface too.

**What passes:**

- Both the rerank and embeddings 429 responses map to `provider_rate_limit`, raised out of the
  respective node.
- The `Authorization: Bearer <api_key>` header is present on both requests.

**What fails:**

- The 429 misclassified as `provider_unavailable` (the bug the §8.2 *Errors* enumeration pins) or any
  other §7 category.
- The adapter retries / loops on the 429 instead of raising.
