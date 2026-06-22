# 0078: Jina Retrieval-Provider Wire Mapping (rerank + embedding)

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-21
- **Accepted:**
- **Targets:** spec/retrieval-provider/spec.md **§8 Wire-format mappings** (the section introduced by
  0077) — add **§8.2 Jina** covering `/v1/rerank` and `/v1/embeddings` on the hosted Jina API, and
  realizing 0077's `input_type` knob via Jina's native wire `task` parameter. **No protocol change**
  (the `input_type` field and the §8 section are both 0077's); **no renumber** (§8.2 appends after
  §8.1 TEI). Plus new conformance fixtures under `spec/retrieval-provider/conformance/`. This proposal
  also **corrects the §2 `return_documents` parenthetical** (text from 0060) in the same spec edit —
  Jina's wire default is `true`, not `false` (see *Note on 0060*); the factual fix is folded into this
  proposal's accept, not a separate PATCH.
- **Related:** 0077 (introduces §8 *Wire-format mappings* + §8.1 TEI + the `input_type` knob this
  reuses — 0078 depends on 0077 and is accepted after it), 0059 (embedding protocol), 0060 (rerank
  protocol — Jina `/v1/rerank` realizes it near 1:1), 0037 / 0038 (llm-provider per-vendor
  wire-mapping precedent)
- **Supersedes:**

## Summary

The second retrieval-provider wire mapping (after 0077's TEI), and the first **hosted-vendor** one:
Jina AI's `/v1/rerank` and `/v1/embeddings`. Three things make it a tight follow-on to 0077:

1. **Jina rerank maps almost 1:1 onto 0060.** 0060's `RerankProvider` shapes were modeled on the
   hosted-vendor wire (Cohere / Voyage / Jina), and Jina is the closest fit: request
   `{model, query, documents, top_n, return_documents}` and response
   `{results: [{index, relevance_score, document?}], usage: {total_tokens}}` line up directly with
   0060's `query` / `documents` / `top_k` / `return_documents` / `results` /
   `ScoredDocument{index, relevance_score, document}`. No client-side batch chunking (Jina is hosted
   and batches server-side — the mandatory chunk-and-stitch was a TEI-specific concern).

2. **It realizes 0077's `input_type` on a wire parameter — the cross-vendor payoff.** Where TEI
   realized `input_type` via a server-side `prompt_name`, Jina realizes it via its native `task` field
   (`input_type="query"` → `task="retrieval.query"`; `"document"` → `task="retrieval.passage"`). Same
   declared `EmbeddingRuntimeConfig.input_type` knob (0077), a second wire realization — demonstrating
   the knob was correctly placed on the protocol, not in a single mapping.

3. **Hosted-vendor construction.** Unlike self-hosted TEI (per-deployment `base_url`), Jina is one
   hosted API (`https://api.jina.ai`) reached with a `Bearer` API key; the provider binds the API key
   + the bound model, with `base_url` defaulting to the Jina endpoint (override for proxies / private
   gateways). A Jina `EmbeddingProvider` and a Jina `RerankProvider` remain distinct instances (one
   model each), but share the one hosted endpoint.

## Motivation

**Completes the rerank/embed mapping catalog across the self-hosted ↔ hosted axis.** 0077 lands the
self-hosted runtime (TEI); 0078 lands a major hosted vendor (Jina), giving adopters a clean OA-native
path whether they self-host or call a managed API — the retrieval-provider analogue of llm-provider
covering both the OpenAI-compatible §8.1 surface and the hosted Anthropic / Gemini §8.2 / §8.3
mappings.

**Proves the `input_type` knob generalizes.** A cross-vendor knob justified by "Cohere / Voyage / Jina
all have it" should be demonstrated on at least one hosted vendor's wire, not only TEI's client-side
prefix. Jina's `task` is that demonstration, and it is the idiomatic, server-side realization the
hosted vendors share.

**Jina is a first-class retrieval vendor.** Jina ships both a competitive reranker family
(`jina-reranker-v2` / `-v3`, multilingual) and a strong asymmetric embedding family
(`jina-embeddings-v3` / `-v4` / `-v5`, with `task`-driven query/passage representations and Matryoshka
`dimensions`) — exactly the two-stage retrieval surface 0059 / 0060 target.

## Proposed change

Add **§8.2 Jina** to the §8 *Wire-format mappings* section (0077). Jina's `gen_ai.system` identifier
is `"jina"` (per the observability §5.5.8 / §5.5.13 "identify the wire surface, not the model
developer" convention). Wire shapes below were **verified against the Jina OpenAPI on 2026-06-21**;
the verified versions are recorded in `docs/compatibility.md` at Accept.

- **Construction.** A Jina provider instance binds an **API key** (sent as `Authorization: Bearer
  <key>`) + the bound model identifier (§3 / §5 per-instance binding), with **`base_url` defaulting to
  `https://api.jina.ai`** (override for a proxy / private gateway). A Jina `EmbeddingProvider`
  (`/v1/embeddings`) and a Jina `RerankProvider` (`/v1/rerank`) are distinct instances (one model
  each) sharing the hosted endpoint.
- **`/v1/rerank`** — `POST {base_url}/v1/rerank` with
  `{"model": str, "query": str, "documents": [str], "top_n"?: int, "return_documents": <bool>, "truncation": false}`.
  Maps onto 0060: `documents` ← `documents`, `top_n` ← `top_k`, `return_documents` ← the
  `RerankRuntimeConfig.return_documents` value (**sent explicitly** — see *Note on 0060*). Response
  `{model, usage: {total_tokens}, results: [{index, relevance_score, document?}]}` maps onto 0060's
  `results` (`index` → `ScoredDocument.index`, `relevance_score` → `relevance_score`, `document` →
  `document`); `usage.total_tokens` → `RerankUsage.input_tokens` (Jina meters rerank by tokens, not
  search units). Results are returned ranked, but the mapping applies 0060's "sort if the provider
  didn't" invariant regardless.
- **`/v1/embeddings`** — `POST {base_url}/v1/embeddings` with
  `{"model": str, "input": [str], "task"?: str, "dimensions"?: int, "truncate": false}`. **`input_type` realization:**
  the mapping sets Jina's native **`task`** from `input_type` — `"query"` → `"retrieval.query"`,
  `"document"` → `"retrieval.passage"` — so Jina applies the model-appropriate query/passage
  representation server-side; `input_type` absent ⇒ `task` omitted (Jina's model default). The mapping
  recognizes a **closed `input_type` set** (`query` / `document` only); an unrecognized value is a
  pre-send `provider_invalid_request` (§7), and Jina's non-retrieval tasks (`text-matching` /
  `classification` / `separation`) are reached via the extras-pass-through bag (a `task` passthrough),
  not `input_type` — widening `input_type`'s normative value space is a protocol-level (0077) change,
  deferred until a consumer needs it. `EmbeddingRuntimeConfig.dimensions` → Jina's `dimensions`
  (Matryoshka truncation) when set. Response
  `{model, usage, data: [{index, embedding}]}` → the `EmbeddingResponse` vectors in input order.
- **`truncation` / `truncate` (fail-loud).** Jina names the flag `truncation` on `/v1/rerank` and
  `truncate` on `/v1/embeddings` (vendor inconsistency); the mapping sends the per-endpoint flag
  `false` so an over-length input **errors rather than being silently truncated** (consistent with
  0077 §8.1's TEI fail-loud posture).
- **Errors** — Jina HTTP failures map to the §7 categories per the shared enumeration: `401` →
  `provider_authentication`; `429` (rate limit) / `5xx` → `provider_unavailable`; unknown model
  (`422` / `404`) → `provider_invalid_model`; over-length / malformed request (`422`) →
  `provider_invalid_request`; malformed response → `provider_invalid_response`.

### Note on 0060 (`return_documents` default)

0060 §2 states "Cohere, Voyage AI, Jina AI all expose `return_documents` defaulting `False`." Verified
2026-06-21: Cohere and Voyage default `false`, but **Jina's wire `return_documents` defaults `true`**.
This does **not** change any normative OA behavior — `RerankRuntimeConfig.return_documents` still
defaults `False` (0060) — but the Jina mapping MUST send `return_documents` **explicitly** (not rely
on Jina's wire default) so OA's default-`False` is honored. **This proposal folds in the correction:**
the editable spec §2 wording is fixed in the same accept that adds §8.2 — 0060's immutable *proposal*
text is untouched; only the spec's §2 parenthetical changes. Corrected reading: Cohere and Voyage
expose `return_documents` defaulting `false`, **Jina defaults `true`**, and OA's
`RerankRuntimeConfig.return_documents` defaults `False` with mappings sending it explicitly where the
wire default differs.

## Conformance test impact

New fixtures under `spec/retrieval-provider/conformance/` (numbers assigned at Accept; appended after
the 0077 TEI set):

- **Jina `/v1/rerank` mapping** — request carries `Authorization: Bearer`, `query`, `documents`,
  `return_documents` (explicit), `truncation: false`; response `results` assemble to 0060's sort +
  valid-index invariants; `usage.total_tokens` → `RerankUsage.input_tokens`.
- **Jina `return_documents` honors the OA default** — OA `return_documents=False` ⇒ the wire request
  sends `return_documents: false` (overriding Jina's `true` wire default); `True` ⇒ `true` and the
  echoed `document` populates `ScoredDocument.document`.
- **Jina `/v1/embeddings` `input_type` → `task`** — `input_type="query"` ⇒ wire `task="retrieval.query"`;
  `"document"` ⇒ `"retrieval.passage"`; absent ⇒ `task` omitted. `dimensions` → wire `dimensions`.
- **Jina `truncation`/`truncate` fail-loud** — an over-length input surfaces `provider_invalid_request`.

## Versioning

**MINOR bump** (pre-1.0), additive only: §8.2 is a new wire mapping; no protocol surface changes
(`input_type` and §8 are 0077's), no renumber. The reference implementation gains a Jina embed +
rerank provider (HTTP client + API-key auth + the `task` realization). Tentative spec version target
deferred to Accept (sequenced after 0077's accept, since §8 must exist first).

## Alternatives considered

1. **Rerank-only (defer embed).** Reasonable — rerank is the near-1:1 win — but Jina's embedding
   family is first-class and its `task` parameter is precisely the second `input_type` realization
   that justifies 0077's knob, so covering both in one mapping is higher-value and not much larger.
2. **`input_type` → `task` via the extras bag instead of the declared knob.** Reject — defeats the
   purpose of 0077's declared `input_type`; the whole point is one declared knob realized per mapping.
3. **A dedicated `jina-provider` capability.** Reject — Jina is a wire mapping of the existing
   `EmbeddingProvider` / `RerankProvider` contracts, exactly as TEI (§8.1) and the llm-provider
   §8.2 / §8.3 hosted mappings are.
4. **Relying on Jina's wire defaults (`return_documents`, `task`).** Reject — send `return_documents`
   explicitly (Jina's `true` default disagrees with OA's `False`) and derive `task` from `input_type`;
   relying on vendor defaults would silently diverge from the OA contract.

## Open questions

None remaining at draft time. Both surfaced during drafting are resolved in the §8.2 text above
(collected here for retrieval).

**Resolved at Draft:**

- **`usage.total_tokens` → `RerankUsage`** — maps to `input_tokens` (rerank has no output tokens, so
  all tokens are input; Jina meters by tokens, not Cohere-style `search_units`, which is left unset).
  No `RerankUsage` change.
- **Embedding `task` value space** — the Jina mapping recognizes a **closed `input_type` set**
  (`query` / `document` → `retrieval.query` / `retrieval.passage`); an unrecognized value is a
  pre-send `provider_invalid_request` (0077's closed-set option). Jina's non-retrieval tasks
  (`text-matching` / `classification` / `separation`) ride the extras bag (`task` passthrough);
  widening `input_type`'s normative value space is a protocol-level (0077) change, deferred until a
  consumer needs it.

## Out of scope

- **Multi-modal Jina inputs** — Jina accepts image / PDF / video / audio docs (`jina-clip`,
  `jina-embeddings-v4`/`v5` omni) and `jina-colbert` multi-vector / late-interaction outputs. Text +
  dense vectors only, per 0059 / 0060.
- **`late_chunking`, `embedding_type` (binary / base64 / ubinary), `normalized=false`** — Jina-specific
  knobs ride the extras-pass-through bag; not declared protocol fields.
- **Other hosted vendors** — Cohere, Voyage AI rerank/embed mappings remain deferred (retrieval-provider
  §11 *Out of scope*); each realizes `input_type` on its own wire.
