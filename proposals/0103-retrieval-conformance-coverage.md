# 0103: Retrieval conformance coverage — §8.3 over-cap, `raw`, and the count-vs-token boundary

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-07-18
- **Targets:** spec/retrieval-provider/spec.md **§8.3** (a prose clarification: the summed-token ceiling is
  provider-enforced fail-loud, not a chunking trigger). Conformance: a new **§8.3 OpenAI over-cap**
  chunk-and-stitch fixture (043, mirroring 037 Cohere / 038 TEI), and **`raw`** assertions closing the §8.3
  OpenAI `raw` gap (the TEI / Cohere / Jina mappings already assert `raw`).
- **Related:** 0092 (the general §8 batch-chunking rule this covers for §8.3), 0093 (nullable usage — the
  stitched-usage assertion), 0096 (the `raw` `dict | list` + chunk-stitch `raw = list of per-request responses`
  rule this exercises)
- **Supersedes:**

## Summary

Two accepted behaviors are unexercised on the **§8.3 OpenAI mapping**, so a conforming §8.3 implementation can
get them wrong and still pass the retrieval suite:

1. **The §8.3 OpenAI 2048-input cap.** 0092 specifies that every capped embedding mapping chunk-and-stitches
   over its per-call cap. Over-cap fixtures exist for Cohere (037) and TEI (038) — but **not** OpenAI (§8.3). An
   implementation can ship §8.3 sending the whole over-cap `input` list un-chunked and pass the entire suite.
2. **§8.3 OpenAI `raw` (0096).** `raw` is asserted for the TEI, Cohere, and Jina mappings — including the
   chunk-and-stitch `raw = list of per-request responses` case (037 / 038 / 042) and single-request `raw` (017)
   — but **not** for the §8.3 OpenAI mapping: no OpenAI fixture asserts `raw`. So 0096's `raw` behavior is
   verified for every mapping except §8.3, the same coverage hole as its over-cap cap.

This proposal adds the missing fixtures, plus one prose clarification of a boundary §8.3 states ambiguously: the
summed-token ceiling OpenAI enforces alongside the 2048-input cap is **not** a chunking trigger — the §8
batch-chunking rule is count-based, and an over-token request fails loud as `provider_invalid_request`.

No behavior changes. This is coverage of, and a clarification to, already-accepted rules.

## Motivation

### Both coverage holes are on the §8.3 OpenAI mapping

**§8.3 over-cap.** §8's *Batch chunking* rule (added by 0092) applies to every capped embedding mapping; §8.3
notes OpenAI's cap is 2048 inputs. But the conformance set exercises chunk-and-stitch only for Cohere (037,
96-input cap) and TEI (038). Nothing drives the §8.3 path, so an implementation that omits chunking on the
OpenAI mapping — sending 3000 inputs in one over-cap request — passes conformance and only fails against a live
provider. A cross-impl fixture is the only thing that closes this for a second implementation.

**§8.3 `raw`.** 0096 widened `EmbeddingResponse.raw` / `RerankResponse.raw` to the verbatim `dict | list` and
pinned that a chunk-and-stitch call's `raw` is the **list** of per-request responses (a single-request call's
`raw` is that one response, not a one-element list). This is asserted for TEI, Cohere, and Jina (037 / 038 / 042
for the list case, 017 for single-request) — but the §8.3 OpenAI mapping has **no** `raw` assertion. An OpenAI
implementation could wrap, reshape, or one-element-wrap `raw` and pass.

### The count-vs-token ambiguity

§8.3 says the mapping "enforces a per-call cap of 2048 inputs (plus a summed-token ceiling); an over-cap call
chunk-and-stitches per the §8 rule." A reader can misread "over-cap" as covering the token ceiling too. It does
not: §8's rule triggers only on "a maximum **input count** per request." A call whose chunks are each ≤2048
inputs but together exceed the token ceiling is not sub-chunked — the provider rejects the over-token request
and it surfaces as `provider_invalid_request` (§7). OA does not mandate client-side token estimation:
tokenization is model-specific and would diverge across implementations, and OA forwards intent and lets the
provider enforce its own vendor-internal limits (the §6 range-validation posture). Making this explicit prevents
an implementation from adding token-based sub-chunking and diverging.

## Proposal

### 1. §8.3 prose — the count-vs-token boundary

Clarify §8.3's cap sentence: the §8 batch-chunking rule is **count-based** and addresses the 2048-**input** cap
only. The summed-token ceiling is **not** a chunking trigger; a call whose consecutive ≤2048-input chunks
together exceed the token ceiling MUST NOT be sub-chunked by an estimated token count — the over-token request
is sent and the provider's rejection surfaces as `provider_invalid_request` (§7), fail-loud, with no partial or
truncated result. The mapping performs no client-side token estimation.

### 2. Fixture 043 — §8.3 OpenAI over-cap chunk-and-stitch

Mirror 037 / 038 for the §8.3 OpenAI-compatible `/v1/embeddings` mapping: a caller `input` exceeding 2048
produces consecutive ≤2048 requests (e.g. 2049 → sizes 2048, 1), each with **every request field but `input`
identical** (model, `dimensions` when set, extras), vectors **stitched in input order** across the chunk
boundary, `EmbeddingUsage.input_tokens` **summed** across chunks (per 0093), and `EmbeddingResponse.response_id`
the **first** chunk's id. The mapping MUST NOT send an over-cap request.

### 3. §8.3 OpenAI `raw` assertions (0096 coverage)

Close the OpenAI `raw` gap (TEI / Cohere / Jina already assert `raw`), pinning both 0096 shapes for §8.3:

- **Chunk-and-stitch `raw` is a list.** Fixture 043 asserts `EmbeddingResponse.raw` is the ordered **list** of
  the per-request response bodies (one entry per chunk, request order) — the OpenAI analogue of 037 / 038.
- **Single-request `raw` is the bare response.** Augment one existing single-request OpenAI fixture (023–027) to
  assert `raw` is that one verbatim response object, not a one-element list.

### 4. Conformance

Fixture 043 (new) plus the `raw` assertions on the augmented fixtures. No fixture is removed or re-keyed; the
augmented fixtures gain assertions on an already-populated field.

## Versioning

**MINOR** (whole-spec SemVer), expected as a batch accept. **Non-breaking**: the §8.3 clarification states
already-intended behavior, and the fixtures exercise already-accepted 0092 / 0096 rules — a conforming
implementation already satisfies them (any that does not was already non-conforming against the prose).

## Open questions

- None. The fixtures pin behavior the prose already mandates.
