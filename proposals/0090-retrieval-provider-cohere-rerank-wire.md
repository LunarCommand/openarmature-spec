# 0090: Cohere Rerank Wire Mapping

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-29
- **Targets:** spec/retrieval-provider/spec.md **§8 Wire-format mappings** (the section introduced by
  0077) — add **§8.4 Cohere** covering `POST /v2/rerank` on the hosted Cohere API, the rerank analogue of
  0079 (OpenAI-compatible embeddings) and the **rerank-only** counterpart to the Jina mapping (§8.2).
  **No protocol change** (the §8 section is 0077's; rerank's `RerankProvider` / `RerankResponse` /
  `ScoredDocument` shapes are 0060's), **no renumber** (§8.4 appends after §8.3). Also **reconciles §11
  *Out of scope*** — the per-vendor deferred list still names Cohere rerank as deferred and (stale since
  0078 / 0079 shipped) still lists the already-shipped Jina rerank and OpenAI / Jina embeddings; the
  same accept removes Cohere rerank and corrects the stale inclusions. Plus new conformance fixtures
  under `spec/retrieval-provider/conformance/`.
- **Related:** 0060 (rerank protocol — this realizes it on a concrete wire and **backs 0060's
  Cohere-shaped reference reranker**, which currently rests on an un-backed stand-in), 0078 (Jina — the
  sibling hosted rerank wire mapping this most closely mirrors), 0079 (OpenAI-compatible embeddings —
  the "rerank analogue of 0079" framing, and the **no-op-knob precedent** this reuses for
  `return_documents`), 0077 (introduces §8 *Wire-format mappings*), 0006 (llm-provider per-vendor
  wire-mapping precedent)
- **Supersedes:**

## Summary

The first **rerank-only** wire mapping, and the one that **closes the rerank reference-provider gap**:
Cohere's `POST /v2/rerank`. Three properties define it:

1. **It backs 0060's reference reranker.** 0060 ships a Cohere-shaped reference `RerankProvider` to make
   the rerank protocol self-testable (driving the protocol fixtures 006–012 and the observability
   fixtures 099–108, with `gen_ai.system: "cohere"`), but — unlike the embedding side, where
   0079's OpenAI-compatible `/v1/embeddings` mapping backs the reference OpenAI-compatible
   `EmbeddingProvider` — **no §8.x wire backs that reranker.** §8.4 closes the asymmetry by pinning the
   Cohere wire that reranker speaks: the reference reranker pre-satisfies the **new §8.4 wire fixtures**,
   exactly as the OpenAI-compatible embedding reference pre-satisfies 0079. The existing capability /
   observability fixtures (006–012 / 099–108) are *not* re-pointed at the wire — they keep exercising the
   runtime-agnostic protocol against a synthetic mock (including the echo-variance invariant real Cohere
   doesn't surface); see *Note on the 0060 stand-in fixtures*.

2. **Cohere v2 is the minimal rerank wire — and that exercises 0079's no-op-knob path, not a new knob.**
   The verified `/v2/rerank` response carries `index` + `relevance_score` only — **no echoed document
   text**, and the request has **no `return_documents` field**. So OA's `RerankRuntimeConfig.return_documents`
   is simply **not realized** on this wire: an absent realization is correct, the mapping leaves
   `ScoredDocument.document` null regardless of the config value, and it does **not** error — the precise
   "knob has no wire to land on, so it's a silent no-op" path 0079 established for `input_type` on the
   symmetric OpenAI wire. §6 already forbids fabricating the echo from the input documents, so callers
   recover the text via `documents[result.index]`.

3. **`search_units` is the usage surface — the mirror image of Jina.** Cohere meters rerank in
   `meta.billed_units.search_units`, the field 0060's `RerankUsage.search_units` was designed for; the
   Cohere mapping populates it and leaves `RerankUsage.input_tokens` null — the exact inverse of Jina
   (§8.2), which populates `input_tokens` and leaves `search_units` null. The two hosted mappings
   together exercise both arms of 0060's deliberately-messy `RerankUsage`.

Rerank-only: Cohere also exposes an embeddings API (`/v2/embed`), but the gap this proposal closes is
rerank's missing wire backing; a Cohere embeddings mapping is a separate future mapping (mirroring 0079
being embeddings-only).

## Motivation

**Closes the rerank reference-provider gap and restores embed/rerank symmetry.** After 0077 / 0078 /
0079, every embedding reference path is backed by a wire proposal, but 0060's rerank reference rests on
a Cohere-shaped stand-in that no §8.x mapping pins. That is the same shape of gap 0079 closed for
embeddings (the reference OpenAI-compatible `EmbeddingProvider` was un-backed until 0079). Backing the
rerank reference is the direct unblock — the reference reranker stops resting on an un-pinned stand-in
wire and gains the real-wire backing 0077 / 0078 / 0079 already gave every embedding reference path.

**Cohere is the canonical hosted reranker.** Cohere's rerank model family is the de-facto reference
reranker the rest of the ecosystem benchmarks against, and Cohere is one of only two of 0060's surveyed
hosted providers (with Voyage) that meter rerank in search units rather than tokens — so the Cohere
mapping is the one that genuinely exercises `RerankUsage.search_units` and the OTel
`openarmature.rerank.search_units` conditional-emission branch (§5.5.13), which Jina's token-metered
mapping leaves unexercised.

**Completes the rerank wire catalog across the self-hosted ↔ hosted axis.** §8.1 (TEI) lands the
self-hosted runtime; §8.2 (Jina) lands a hosted vendor that meters by tokens and *does* echo documents;
§8.4 (Cohere) lands the hosted vendor that meters by search units and *does not* echo — together the
three pin the full spread of rerank wire behaviors a real retrieval stack draws from.

## Proposed change

Add **§8.4 Cohere** to the §8 *Wire-format mappings* section (0077). Cohere's `gen_ai.system` identifier
is `"cohere"` (per the observability §5.5.8 / §5.5.13 "identify the wire surface, not the model
developer" convention; this matches the value 0060's observability stand-in fixtures 099–108 already
emit). The `/v2/rerank` wire shapes below were **verified against the Cohere v2 API reference on
2026-06-29**; the verified version is recorded in `docs/compatibility.md` at Accept.

- **Construction.** A Cohere `RerankProvider` binds an **API key** (sent as `Authorization: Bearer
  <key>`) + the bound rerank model identifier (§3 / §5 per-instance binding), with `base_url` defaulting
  to `https://api.cohere.com` (origin only — the `/v2` version stays in the route, consistent with
  §8.2 / §8.3; override for a proxy / private gateway). **Rerank-only** — no `EmbeddingProvider`
  counterpart in this mapping (a Cohere embeddings wire is a separate future mapping; see *Out of
  scope*).
- **`/v2/rerank`.** `POST {base_url}/v2/rerank` with
  `{"model": str, "query": str, "documents": [str], "top_n"?: int}`. `documents` ← `documents` (§5),
  sent as the **string-array** form (Cohere v2 takes strings only — the v1 list-of-objects /
  `rank_fields` form is not used); `top_n` ← `top_k` (§5), omitted when the caller passed `None`. The
  response `{"id": str, "results": [{"index": int, "relevance_score": float}], "meta": {"billed_units": {"search_units": int}}}`
  maps onto 0060's shapes: each `results` entry's `index` → `ScoredDocument.index`, `relevance_score` →
  `ScoredDocument.relevance_score`; `meta.billed_units.search_units` → `RerankUsage.search_units`
  (`RerankUsage.input_tokens` stays null — Cohere does not report a token count); top-level `id` →
  `RerankResponse.response_id` (pinning, for Cohere, the per-vendor `response_id` source that 0060 left
  position-agnostic). Cohere returns results ranked, but the mapping applies §6's "sort if the
  provider didn't" invariant regardless, and enforces §6's valid-`index` / no-duplicate-`index` /
  `len(results) <= top_k` invariants against the response.
- **`return_documents` (not realized — a silent no-op).** The `/v2/rerank` wire has **no
  `return_documents` parameter and never echoes document text** (results carry `index` +
  `relevance_score` only). So OA's `RerankRuntimeConfig.return_documents` (§2) is **not realized** on
  this wire: the mapping does **not** add any wire field for it, leaves `ScoredDocument.document` **null
  on every result regardless of the config value**, and does **not** error when `return_documents=True`
  is requested — the same "knob with no wire to land on is a silent no-op" path §8.3 established for
  `input_type` on the symmetric OpenAI wire. This is consistent with §6's rule that an implementation
  MUST NOT fabricate the echo from the input `documents` list when the provider omits it; callers recover
  the document text via `documents[result.index]` (the `index` field is the load-bearing lookup key).
- **`max_tokens_per_doc` / truncation posture (no fail-loud).** Unlike §8.1 (TEI) and §8.2 (Jina), which
  send a `truncate: false` / `truncation: false` flag so an over-length input **errors** rather than
  being silently truncated, the Cohere `/v2/rerank` wire has **no fail-loud option** — Cohere truncates
  each over-length document server-side to `max_tokens_per_doc` (Cohere's wire default `4096`). The
  Cohere mapping therefore does **not** realize §8.1 / §8.2's fail-loud posture (the wire cannot express
  it); OA has no declared truncation field, so `max_tokens_per_doc` rides the **extras-pass-through bag**
  (absent ⇒ Cohere's `4096` default applies). This vendor divergence is stated explicitly per charter
  §3.1 principle 8 (transparency over abstraction): a long-document rerank against Cohere is silently
  truncated where the same call against TEI / Jina would fail loud.
- **Errors.** Cohere HTTP failures map to the §7 categories per the shared enumeration: `401` →
  `provider_authentication`; `429` (rate limit) → `provider_rate_limit`; `5xx` →
  `provider_unavailable`; unknown model (`404`) → `provider_invalid_model`; malformed / invalid
  request (`400`) → `provider_invalid_request`; malformed response → `provider_invalid_response`.
  (Cohere uses `400` for an invalid request body — not the `422` Jina §8.2 returns; verified against
  the Cohere errors reference.)

### Note on the 0060 stand-in fixtures (006–012 / 099–108)

0060's reference reranker is a **Cohere-shaped stand-in**: fixture 006's header frames the suite's
response shape as a stand-in pending the per-vendor wire-format work, and the stand-in's mock response
carries an **optional
`document` echo** (exercised by the §6 echo-variance invariant in fixture 012) and a `return_documents`
knob. Real Cohere v2 carries **neither** — it never echoes document text and has no `return_documents`
field. This proposal **does not change those fixtures.** They are *capability* fixtures: they validate
the runtime-agnostic `RerankProvider` protocol (sort, valid-index, top_k, per-result echo-variance
preservation) and the observability mapping against a synthetic provider, and a *hypothetical* echoing
provider exercises the §6 echo-preservation invariant legitimately regardless of whether any one real
vendor echoes. The accurate no-echo v2 shape is pinned by the **new §8.4 wire fixtures** (below). The
discrepancy is called out here so implementations do not read the stand-in's `document` echo as a Cohere
v2 wire claim — it is not.

## Conformance test impact

New fixtures under `spec/retrieval-provider/conformance/` (numbers assigned at Accept; appended after the
0079 OpenAI-compatible set 023–027). Following the 0079 precedent (and the §8.2 Jina precedent), these
are **separate wire fixtures** that capture the byte-level wire request (`expected_wire_request`) and the
v2 response shape — the existing capability stand-in fixtures (006–012 / 099–108) are left unchanged:

- **Cohere `/v2/rerank` mapping** — request carries `Authorization: Bearer`, `model`, `query`,
  `documents` (string array), and `top_n` (from `top_k`); the response `results` assemble to §6's sort +
  valid-index invariants; `meta.billed_units.search_units` → `RerankUsage.search_units`; top-level `id`
  → `RerankResponse.response_id`.
- **`return_documents` is a no-op** — `rerank(config={return_documents: True})` produces a wire request
  **byte-identical** to the default (no `return_documents` field), and **every** `ScoredDocument.document`
  is null (Cohere v2 echoes nothing); the mapping does not error. The negative-space companion to 0079's
  "`input_type` is a no-op" fixture.
- **`search_units` usage** — `meta.billed_units.search_units` → `RerankUsage.search_units`;
  `RerankUsage.input_tokens` is null (the inverse of the Jina mapping, which populates `input_tokens` and
  leaves `search_units` null).
- **`top_k` → `top_n`** — a supplied `top_k` maps to the wire `top_n`; an absent `top_k` (`None`) omits
  `top_n` from the request.
- **Rate-limit error mapping** — a Cohere `429` surfaces `provider_rate_limit` (§7), parallel to the
  Jina `022` rate-limit fixture.

## Versioning

**MINOR bump** (pre-1.0), additive only: §8.4 is a new wire mapping; no protocol surface changes (the §8
section is 0077's, the rerank shapes are 0060's), no renumber. The §11 *Out of scope* reconciliation is
a stale-list correction with no behavioral effect. The reference implementation gains a Cohere rerank
provider (HTTP client + API-key auth). Tentative spec version target deferred to Accept (sequenced in the
retrieval block; §8 already exists, so no ordering dependency on a sibling proposal).

## Alternatives considered

1. **Promote the stand-in fixtures (006–012 / 099–108) into the Cohere wire** — fold
   `expected_wire_request` capture onto the existing fixtures rather than adding separate wire fixtures.
   **Reject** — this is the same two-layer choice 0079 made (it added 023–027 rather than retrofitting
   the 001–005 embedding capability fixtures). Keeping the capability fixtures runtime-agnostic and
   adding dedicated wire fixtures preserves the layering: the capability fixtures assert the protocol
   contract against a synthetic provider; the wire fixtures assert the concrete Cohere request/response.
   Retrofitting would also force the stand-in's synthetic `document` echo to be reconciled against the
   real no-echo wire mid-fixture, conflating the two layers.
2. **Realize `return_documents=True` by echoing from the input `documents` list (client-side).**
   **Reject** — §6 explicitly forbids fabricating the echo (it would mask provider-side document
   transformations and conflate the caller's input with the provider's echo); and Cohere v2 performs no
   such transformation to surface. Leave `ScoredDocument.document` null and let callers index into their
   own `documents`.
3. **Error when `return_documents=True` is requested against a wire that can't honor it.** **Reject** —
   hostile, and inconsistent with the §8.3 `input_type`-no-op precedent (an unrealizable knob is a silent
   no-op, not an error). The caller's intent ("I want the text back") is already satisfied by the
   `index` lookup.
4. **Include a Cohere embeddings half (`/v2/embed`).** **Reject** — the gap this proposal closes is
   rerank's missing wire backing. Cohere embeddings is a real surface but a separate mapping, exactly as
   0079 is embeddings-only and 0078's embed/rerank pairing was a Jina-specific convenience. Bundling
   would widen the proposal past the rerank reference-provider gap it targets.
5. **Send a synthesized fail-loud truncation flag.** **Reject** — the Cohere `/v2/rerank` wire has no
   such field; `max_tokens_per_doc` is a truncation *limit*, not a fail-loud toggle. Inventing a flag
   Cohere doesn't accept would diverge from the verified wire. Document the divergence (no fail-loud;
   server-side truncation to `max_tokens_per_doc`) transparently instead.
6. **Map to Cohere v1 (`/v1/rerank`) instead of v2.** **Reject** — v2 is the current API; v2's
   strings-only `documents` and `{id, results, meta.billed_units.search_units}` response are the simpler,
   forward-looking shape, and the value 0060's stand-in already anticipates (`gen_ai.system: "cohere"`,
   `search_units` metering). v1's list-of-objects / `rank_fields` form and `return_documents` echo are
   legacy.
7. **A dedicated `cohere-provider` capability.** **Reject** — Cohere rerank is a §8.x wire mapping of the
   existing `RerankProvider` contract, exactly as TEI (§8.1) and Jina (§8.2) are, and as the llm-provider
   §8.x hosted mappings are.

## Open questions

**Open — awaiting a maintainer ruling (at Accept):**

- **Fixture layering — separate wire fixtures vs. promoting the stand-in.** Whether to add *separate*
  Cohere-wire fixtures and leave the 0060 capability stand-in (006–012 / 099–108) unchanged, or to
  *promote* that stand-in into the Cohere wire by folding `expected_wire_request` capture onto the
  existing fixtures. The two options and the trade-off are laid out in Alternatives 1.
  **Recommendation: separate** (the 0079 precedent — it added 023–027 rather than retrofitting the
  001–005 embedding capability fixtures — and the layering it preserves). The draft's *Conformance test
  impact* section is written to the separate-fixtures shape; if the ruling is "promote," that section and
  Alternatives 1 flip and the existing fixtures gain a request-side wire assertion.

**Resolved (during drafting / review):**

- **Error-status-code mapping.** RESOLVED: verified against the Cohere errors reference — `401` →
  `provider_authentication`, `404` (unknown model) → `provider_invalid_model`, `400` (invalid body) →
  `provider_invalid_request`, `429` → `provider_rate_limit`, `5xx` → `provider_unavailable`. Cohere does
  **not** use `422` (a Jina §8.2 idiom that an earlier draft had carried over); the §8.4 text uses `400`.
- **Per-vendor `response_id` source for Cohere.** RESOLVED: the top-level `id` field. This pins, for
  Cohere, the per-vendor `response_id` sourcing that 0060 explicitly left position-agnostic (deferring it
  to the wire-mapping proposals).
- **The stand-in `document` echo vs. real Cohere v2.** RESOLVED: the 0060 capability stand-in fixtures
  (006–012 / 099–108) are left unchanged and reframed as runtime-agnostic protocol tests; the accurate
  no-echo v2 shape is pinned by the new §8.4 wire fixtures. See *Note on the 0060 stand-in fixtures*.
  (Contingent on the fixture-layering ruling above.)
- **Whether to land a Cohere `/v2/embed` mapping in the same proposal.** RESOLVED: no — rerank-only (see
  Alternatives 4); the active pull is the rerank reference backing.

**Deferred to Accept (alignment, not design):**

- **`gen_ai.system`** — `"cohere"` identifies the wire surface and matches the value the 0060
  observability stand-in fixtures (099–108) already emit; confirm the exact match when writing §8.4.
- **§11 *Out of scope* reconciliation** — at Accept, remove Cohere rerank from the per-vendor deferred
  list and correct the list's stale inclusion of the already-shipped Jina rerank and OpenAI / Jina
  embeddings (a 0078 / 0079 carry-over the per-accept sweep missed).

## Out of scope

- **Cohere embeddings (`/v2/embed`).** A separate future wire mapping; this proposal is rerank-only.
- **`max_tokens_per_doc`, `priority`, and other Cohere-specific knobs as declared protocol fields.** They
  ride the extras-pass-through bag; not declared protocol fields.
- **Cohere v1 (`/v1/rerank`).** v2 only (see Alternatives 6).
- **Fail-loud over-length handling for Cohere.** Not expressible on the Cohere wire; documents are
  truncated server-side to `max_tokens_per_doc`.
- **Multi-modal rerank, streaming rerank, score normalization across providers.** Per 0060 — text-only,
  non-streaming, provider-native scores surfaced as-returned.
- **Other rerank vendors (Voyage AI).** Remain deferred (retrieval-provider §11 *Out of scope*); each
  realizes its own wire and usage surface.
