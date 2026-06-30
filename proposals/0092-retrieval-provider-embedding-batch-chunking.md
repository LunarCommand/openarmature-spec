# 0092: Embedding-Mapping Batch Chunking (general §8 rule)

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-29
- **Targets:** spec/retrieval-provider/spec.md **§8 Wire-format mappings** — add a **general
  batch-chunking rule** to the §8 preamble governing every embedding mapping: when a provider enforces a
  maximum input count per request, the mapping MUST chunk-and-stitch rather than send an over-cap
  request. This **generalizes the per-input-independence chunk-and-stitch argument** §8.1 already applies
  to TEI *rerank* (0077), extending it to the embedding side across all mappings. Reconciles the
  per-mapping sections to reference the general rule: **§8.4 Cohere** (0091's Cohere-specific embed
  chunking paragraph → the general rule, keeping Cohere's 96 cap), **§8.1 TEI** (its `/embed` inherits
  the rule under `max-client-batch-size`), **§8.3 OpenAI** (the 2048 cap), and notes **§8.2 Jina** as the
  cap-free case the rule exempts. **No protocol change** (the §8 section is 0077's, the embedding shapes
  are 0059's). Resolves the cross-mapping open question logged under retrieval-provider in
  `docs/open-questions.md`. Plus a new conformance fixture under `spec/retrieval-provider/conformance/`.
- **Related:** 0091 (Cohere embeddings — surfaced this gap and specs the Cohere-specific instance this
  generalizes; **0092 is accepted after 0091**, so §8.4 exists to reconcile), 0077 (introduces §8 + the
  TEI **rerank** chunk-and-stitch this generalizes to embeddings), 0078 (Jina — the cap-free mapping),
  0079 (OpenAI — the 2048-cap mapping), 0059 (embedding protocol — `embed()` accepts an
  arbitrary-length input list)
- **Supersedes:**

## Summary

A small cross-mapping rule that closes a gap the embedding wire mappings share: **none of them, except
the Cohere instance 0091 added, says what happens when a caller embeds more inputs than the provider
accepts per request.** `embed()` (§3) takes an arbitrary-length input list, but real embedding endpoints
cap inputs per call — and the cap varies sharply:

| Mapping | Per-call input cap |
|---|---|
| Cohere `/v2/embed` (§8.4) | **96** (fixed) |
| OpenAI `/v1/embeddings` (§8.3) | **2048** (fixed; plus a summed-token ceiling) |
| TEI `/embed` (§8.1) | **`max-client-batch-size`** (deployment-configured; default 32) |
| Jina `/v1/embeddings` (§8.2) | **none** — Jina batches server-side by token count |

Today only §8.4 Cohere (0091) defines the over-cap behavior; §8.1 and §8.3 leave it **undefined**, so a
caller embedding more than 2048 inputs against OpenAI, or more than `max-client-batch-size` against TEI,
hits per-implementation behavior. This proposal lifts 0091's Cohere-specific paragraph into a single
**§8 batch-chunking rule** that governs every embedding mapping uniformly: *when a provider enforces a
per-call input cap, the mapping MUST split into consecutive ≤cap chunks, issue one request per chunk, and
stitch the vectors in input order.* It is the embedding analogue of the rerank chunk-and-stitch §8.1
already specs for TEI, resting on the same property — **each embedding is computed independently of the
others in its batch**, so chunking is transparent.

## Motivation

**The gap is real and recurs per vendor.** 0091 had to spec chunk-and-stitch for Cohere's 96 cap; without
a general rule, the next embedding mapping (and the already-accepted OpenAI and TEI ones) each re-derive
— or silently omit — the same behavior. A single §8 rule defines it once for all mappings, present and
future, and turns "undefined over-cap behavior" into a conformance-checkable contract.

**The cap spread makes a per-mapping-only approach worst.** The caps differ by nearly two orders of
magnitude (TEI 32 ↔ OpenAI 2048) and one mapping (Jina) has none. A caller composing a graph against
several providers shouldn't have to know each mapping's over-cap behavior; the protocol-level contract
("`embed()` takes any-length list") should hold uniformly, with chunking an invisible wire concern.

**The correctness argument is already settled.** §8.1 established that a per-item-independent retrieval
operation can be chunked and stitched without changing results (it did this for TEI rerank, where each
`(query, document)` pair is scored independently). Embeddings have the identical property — each input's
vector is independent of the batch — so the same rule transfers directly. This proposal generalizes an
argument the spec already makes, rather than introducing a new one.

## Proposed change

Add a **batch-chunking rule** to the §8 *Wire-format mappings* preamble (so it governs every §8.x
embedding mapping), and reconcile the per-mapping sections to reference it. Verified per-call caps below
were checked against each provider's API reference on 2026-06-29 and are recorded in
`docs/compatibility.md` at Accept.

- **§8 general rule (new).** When an embedding mapping's provider enforces a **maximum input count per
  request**, and a caller's input list exceeds it, the mapping MUST:
  1. split the inputs into **consecutive chunks of at most the provider's per-call cap**, preserving
     order;
  2. issue **one request per chunk**, with **identical per-call parameters** (model, `input_type` /
     realization, dimensions, `embedding_types`, truncation, etc.);
  3. **stitch** the responses: concatenate the per-chunk vectors **in the original input order**, so the
     §4 one-vector-per-input and input-order invariants hold across the whole call; and
  4. aggregate usage: **sum** the per-chunk `EmbeddingUsage.input_tokens`.

  `EmbeddingResponse.response_id` is the **first chunk's** response id (a single-request call uses that
  request's id). A mapping **MUST NOT** silently send an over-cap request. When a provider enforces **no**
  per-call cap (it batches server-side), no client-side chunking is required. This rule is the embedding
  analogue of the §8.1 TEI rerank chunk-and-stitch and rests on the same per-item-independence property.

- **§8.4 Cohere (reconcile, from 0091).** 0091's *Mandatory batch chunking (96-input cap)* paragraph is
  reduced to: Cohere's per-call cap is **96**; over-cap calls chunk-and-stitch per the §8 rule. The
  algorithm moves to the general rule; only the cap value stays Cohere-specific.

- **§8.3 OpenAI (reconcile, from 0079).** Note OpenAI `/v1/embeddings`' per-call cap of **2048 inputs**
  (plus the provider-enforced summed-token ceiling); over-cap calls chunk-and-stitch per the §8 rule.

- **§8.1 TEI (reconcile, from 0077).** Note that TEI's `/embed` is bounded by the same
  **`max-client-batch-size`** as `/rerank` (the construction `chunk_size`, default 32) and chunks per the
  §8 rule — aligning the embed side with the rerank chunking §8.1 already specs.

- **§8.2 Jina (note).** Jina enforces **no** per-call input cap (it batches server-side by token count),
  so the §8 rule's no-cap branch applies and the Jina embed mapping does not chunk client-side.

## Conformance test impact

New fixture under `spec/retrieval-provider/conformance/` (number assigned at Accept):

- **Embedding over-cap chunk-and-stitch** — a vendor-agnostic fixture: a mapping with a small synthetic
  per-call cap receives an input list exceeding it and MUST issue multiple requests (consecutive ≤cap
  chunks), with the stitched response carrying one vector per input **in input order** and
  `EmbeddingUsage.input_tokens` **summed** across chunks. Asserts the over-cap request is chunked, not
  sent whole.

0091's Cohere `>96-input chunk-and-stitch` fixture remains as the Cohere-specific instance of the same
rule; this fixture pins the **general** contract independent of any one vendor's cap.

## Versioning

**MINOR bump** (pre-1.0), additive: the §8 rule **defines previously-undefined behavior** (over-cap
embedding calls in §8.1 / §8.3 had no specified outcome), so it adds a contract rather than changing an
existing one. No protocol surface change; no renumber. The reference implementation gains client-side
chunking for the OpenAI and TEI embedding providers (the Cohere one from 0091 already has it). Tentative
spec version target deferred to Accept (sequenced **after 0091**, since the §8.4 reconciliation needs
§8.4 to exist).

## Alternatives considered

1. **Per-mapping chunking paragraphs instead of a general rule.** Reject — that is the status quo gap
   (only Cohere has one). Each new mapping would re-derive or omit the behavior; a §8 rule defines it
   once and binds future mappings automatically.
2. **Error on over-cap rather than chunk-and-stitch.** Reject — chunk-and-stitch is transparent (the
   per-input-independence property guarantees identical results) and is the behavior §8.1 already
   mandates for TEI rerank; erroring would break the protocol contract that `embed()` accepts an
   arbitrary-length list and force every caller to pre-chunk.
3. **Put the rule at the protocol layer (§3 / §4) instead of §8.** Reject — per-call caps are wire facts
   (each provider's request schema), not protocol semantics; the chunking that hides them is a
   wire-mapping concern, so §8 is the right home (the protocol contract simply stays "any-length list").
4. **Cover rerank in the same rule (general retrieval chunking).** Reject for this proposal — the rerank
   side is largely already handled (§8.1 specs TEI rerank chunk-and-stitch), and the one unhandled
   hosted rerank cap (Cohere `/v2/rerank`'s ~1000-document figure) is a **soft recommendation**, not a
   hard per-call cap that errors, so it does not need mandatory chunking. Rerank stitching also differs
   (re-base indices, re-apply the §6 sort + `top_k`) and is better kept in the rerank-specific text.
   Out of scope here; revisit if a hard rerank cap surfaces.
5. **Pin each provider's cap as a normative constant.** Reject — TEI's cap is deployment-configured (not
   a fixed number), and hosted caps drift; the **rule** is normative, the cap values are
   verified-at-Accept facts recorded in `docs/compatibility.md` (like other per-vendor wire facts), cited
   per mapping but not frozen into normative MUSTs.

## Open questions

**Resolved (during drafting):**

- **`response_id` when chunked.** RESOLVED: the first chunk's response id (a single-request call uses
  that request's id). A multi-request call has no single provider response id; the first is the
  deterministic choice.
- **Normative vs. informative cap values.** RESOLVED: the chunk-and-stitch *rule* is normative; the
  per-mapping cap *values* are verified-at-Accept facts in `docs/compatibility.md` (Alternatives 5),
  since TEI's is deployment-configured and hosted caps drift.
- **Scope (embed vs. embed + rerank).** RESOLVED: embeddings only (Alternatives 4); the rerank side is
  handled by §8.1 and has no hard hosted cap needing mandatory chunking today.

**Deferred to Accept (alignment, not design):**

- **`docs/open-questions.md` resolution** — at Accept, update the retrieval-provider *"Cross-cutting — §8
  embedding-mapping per-call input caps"* entry to `resolved-by-0092`.
- **§8.4 reconciliation ordering** — confirm 0091 is Accepted before 0092 (0091 itself follows 0090,
  which creates §8.4), so §8.4 Cohere exists to reconcile (otherwise the §8.4 edit drops and only the §8
  rule + §8.1 / §8.3 notes land).

## Out of scope

- **Rerank batch chunking.** Handled per-mapping (§8.1 TEI rerank); no hard hosted rerank cap needs a
  general rule today (Alternatives 4). Cohere `/v2/rerank`'s ~1000-document figure is a soft
  recommendation.
- **The summed-token ceiling** (e.g. OpenAI's per-request token total). Chunking by input *count* does
  not by itself bound total tokens; token-budget-aware chunking is a separate concern and not required
  here (the count cap is the hard per-request limit this rule addresses).
- **Pinning per-vendor cap values as normative constants** (Alternatives 5).
- **Multi-modal / non-text embedding inputs.** Per 0059 — text + dense float vectors only.
