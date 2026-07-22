# 045 — Jina bare `400` maps to `provider_invalid_request`

Proposal 0104 reconciles retrieval-provider §8.2's Jina error enumeration. §8.2 named only `422` (Jina's
over-length / validation status), so a bare `400` fell through to the catch-all `provider_unavailable` —
diverging from the other mappings' treatment of a malformed request — §8.3 / §8.4 map a bare `400` →
`provider_invalid_request`, and §8.1 TEI routes its malformed statuses (`413` / `422`) to that same category —
and from the general §7
semantics. That was wrong on two counts: it diverged from every other mapping, and `provider_unavailable` is a
**transient** category (a caller may retry) while a `400` is a malformed request that will **not** succeed on
retry — a request error misclassified as transient invites a pointless retry loop.

**Spec sections exercised:**

- retrieval-provider §8.2 Jina — *Errors*: a bare `400` → `provider_invalid_request` (as reconciled by 0104),
  distinct from the `422` over-length status (fixture 021).
- retrieval-provider §7 — `provider_invalid_request` is a non-transient request-error category; the mapping
  raises it out of the rerank node rather than the transient `provider_unavailable`.

**Case:**

1. `bare_400_maps_to_provider_invalid_request_not_unavailable` — a `/v1/rerank` call where Jina returns HTTP
   `400`. The adapter classifies it `provider_invalid_request` and raises out of the rerank node; the wire
   request still carries the `Authorization: Bearer` header.

**What passes:**

- The raised category is `provider_invalid_request`, `raised_from` the rerank node.
- The bare `400` is **not** misclassified as the transient `provider_unavailable`.
- The `Authorization: Bearer` header is present on the wire request.

**What fails:**

- Routing a bare `400` to `provider_unavailable` (the pre-0104 catch-all behavior), or to any other §7
  category.
- Swallowing the `400` and returning a (missing) result instead of raising.
