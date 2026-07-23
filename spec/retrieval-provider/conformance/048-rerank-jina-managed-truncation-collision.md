# 048 — managed-field collision, reject arm: extras `truncation` vs Jina `/v1/rerank`'s managed flag

The Jina realization of the llm-provider §6 *Managed-field collision* reject arm, covering the distinct wire-key
**name**: §8.2 Jina names the fail-loud truncation flag `truncation` on `/v1/rerank` (and `truncate` on
`/v1/embeddings` — vendor inconsistency). The mapping sends `truncation: false` explicitly on `/v1/rerank`, so
`truncation` is a managed scalar: an extras-supplied `truncation` conflicting with the managed `false` is
rejected pre-send.

**Spec sections exercised:**

- llm-provider §6 — *Managed-field collision* (reject arm): a conflicting extras value on a managed scalar is
  rejected pre-send `provider_invalid_request`, never dropped or forwarded.
- retrieval-provider §8.2 Jina — `truncation` (the `/v1/rerank` fail-loud flag) is a managed scalar.
- retrieval-provider §7 — `provider_invalid_request` raised pre-send, no wire request issued.

**Cases:**

1. `conflicting_extras_truncation_rejected_pre_send` — `rerank(config={extras: {truncation: true}})`. `true`
   conflicts with the managed `false`; honoring it would silently truncate an over-length `(query, document)`
   pair, yielding a wrong relevance score the mapping fails loud on. The mapping raises
   `provider_invalid_request` pre-send, issues **no** `/v1/rerank` request, and neither drops nor forwards the
   value.
2. `matching_extras_truncation_is_noop` — `rerank(config={extras: {truncation: false}})`. `false` **equals** the
   managed value, so it is a redundant no-op: the normal `/v1/rerank` request goes out with `truncation: false`
   (unduplicated), results returned normally. Discriminates an impl that over-rejects *any* extras `truncation`;
   the boolean `false` shape differs from Cohere's string `"NONE"` (046 case 2), so it is exercised here rather
   than only asserted by analogy.

**Scope.** This fixture covers the distinct `truncation` name on the rerank surface. TEI `/embed`'s distinct
relied-upon-default case is fixture 047.

**What passes:**

- `provider_invalid_request` raised out of the rerank node, no `/v1/rerank` request issued, the conflicting
  value neither dropped nor forwarded.

**What fails:**

- Forwarding a conflicting `truncation: true` onto the wire (defeating fail-loud), or silently dropping it, or
  routing the rejection to any other §7 category.
