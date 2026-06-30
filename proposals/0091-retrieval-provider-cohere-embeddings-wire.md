# 0091: Cohere Embeddings Wire Mapping

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-29
- **Targets:** spec/retrieval-provider/spec.md **§8 Wire-format mappings** — **extend §8.4 Cohere** (the
  section created by 0090) to add the **`POST /v2/embed`** endpoint alongside the existing `/v2/rerank`
  half, so §8.4 covers both Cohere endpoints the way §8.2 Jina covers `/v1/rerank` + `/v1/embeddings`.
  This adds the **third realization of 0077's `input_type` knob** (after TEI's `prompt_name` and Jina's
  `task`) and the **first where the wire field is mandatory**. **No protocol change** (the §8 section is
  0077's, the embedding shapes are 0059's, `input_type` is 0077's), **no renumber** (extends the existing
  §8.4 subsection). The accept also **reconciles 0090's "rerank-only / a Cohere embeddings wire is a
  separate future mapping" sentence** in §8.4 (now satisfied) and the §11 *Out of scope* per-vendor
  deferred list. Plus new conformance fixtures under `spec/retrieval-provider/conformance/`.
- **Related:** 0090 (Cohere rerank wire — **creates §8.4 Cohere, which this extends; 0091 is accepted
  after 0090**), 0059 (embedding protocol — this realizes it on a concrete wire), 0079 (OpenAI-compatible
  embeddings — the sibling hosted embed wire it contrasts with: symmetric, with the `input_type` no-op), 0077 (introduces §8 + the
  `input_type` knob — this is its third, and first mandatory, wire realization; reuses 0078's closed-set
  treatment), 0078 (Jina — the hosted asymmetric embed wire this most closely mirrors, and the
  embed-and-rerank-in-one-vendor-section precedent), 0006 (llm-provider
  per-vendor wire-mapping precedent)
- **Supersedes:**

## Summary

The embedding half of the Cohere wire mapping, completing §8.4 Cohere into a two-endpoint vendor
section (rerank from 0090, embed here) — the structure §8.2 Jina already has. Cohere's `POST /v2/embed`
is a near-1:1 fit for the 0059 embedding protocol, with one property that makes it the most
*interesting* embedding wire in the catalog:

1. **It's the first wire where `input_type` is mandatory.** 0077's `input_type` is an optional
   `EmbeddingRuntimeConfig` field with an "absent ⇒ symmetric default" contract; TEI realizes it via an
   optional `prompt_name`, Jina via an optional `task` (absent ⇒ omitted), and 0079's symmetric OpenAI
   wire doesn't realize it at all. **Cohere v2 `/v2/embed` requires `input_type` on every request.** So
   this mapping is the one that has to define what the *absent* OA value maps to — it cannot omit the
   field. The mapping sends `query` → `search_query`, `document` → `search_document`, and **absent ⇒
   `search_document`** (the bulk-indexing default; the dominant embedding use case is storing document
   vectors). This exercises a corner of 0077's design the other three realizations don't: a wire that
   forces a value where OA allows none.

2. **Embed can fail loud — unlike the Cohere rerank half.** Where 0090's `/v2/rerank` had no fail-loud
   option (Cohere truncates rerank documents server-side to `max_tokens_per_doc`), `/v2/embed` exposes
   `truncate: "NONE"`, which makes an over-length input **error** rather than be silently truncated. The
   embed mapping sends `truncate: "NONE"` — the §8.2 Jina embed fail-loud posture — so the two halves
   of §8.4 Cohere differ deliberately on truncation, each matching what its endpoint actually offers.

3. **Response embeddings are keyed by type.** Cohere returns `embeddings` as an object keyed by
   embedding type (`{"float": [[…], …]}`), not OpenAI's `data: [{embedding}]` array. The mapping requests
   the default `["float"]` type and consumes `embeddings.float` in input order; the other Cohere
   embedding types (`int8` / `uint8` / `binary` / `ubinary` / `base64`) are out of scope (0059 is dense
   float vectors).

## Motivation

**Completes §8.4 Cohere and the hosted-embed catalog.** 0090 landed Cohere rerank; the embedding half is
the natural completion, giving adopters a single Cohere provider pair (embed + rerank) the way §8.2
gives them a Jina pair. With 0079 (OpenAI-compatible), 0078 (Jina), and 0077 (TEI) already shipped, the
hosted-embed catalog then spans the symmetric ecosystem wire (OpenAI), two asymmetric hosted vendors
(Jina, Cohere), and the self-hosted runtime (TEI).

**Proves the `input_type` knob generalizes to a mandatory wire.** 0077 (TEI) and 0078 (Jina) realized
`input_type` on *optional* wire fields (a server-side prompt, a wire `task`); 0079 demonstrated the
*symmetric* no-op. Cohere is the realization that stresses the knob hardest — a wire that **requires**
the query/document distinction. Showing OA's optional `input_type` maps cleanly onto a mandatory field
(with a defined
default for the absent case) is the final evidence that 0077 placed the knob at the right layer.

**Cohere is a first-class embedding vendor, not only a reranker.** Cohere's embedding family ships the
asymmetric `search_query` / `search_document` representations, Matryoshka `output_dimension`, and
multiple output precisions — exactly the asymmetric-embedding surface 0059 / 0077 target, and the
companion to the rerank family 0090 mapped.

## Proposed change

**Extend §8.4 Cohere** (0090) with the `/v2/embed` endpoint. The construction paragraph generalizes to
cover both a Cohere `EmbeddingProvider` (`/v2/embed`) and a Cohere `RerankProvider` (`/v2/rerank`) as
distinct instances sharing the hosted endpoint (the §8.2 Jina pattern); `gen_ai.system` stays `"cohere"`
for both. The `/v2/embed` wire shapes below were **verified against the Cohere v2 API reference on
2026-06-29**; the verified version is recorded in `docs/compatibility.md` at Accept.

- **Construction.** A Cohere `EmbeddingProvider` binds an **API key** (`Authorization: Bearer <key>`) +
  the bound embedding model identifier (§3 / §5 per-instance binding), with `base_url` defaulting to
  `https://api.cohere.com` (origin only — the `/v2` version stays in the route, as for the rerank half).
  A Cohere `EmbeddingProvider` and a Cohere `RerankProvider` are distinct instances (one model each)
  sharing the hosted endpoint.
- **`/v2/embed`.** `POST {base_url}/v2/embed` with
  `{"model": str, "input_type": str, "texts": [str], "embedding_types": ["float"], "truncate": "NONE", "output_dimension"?: int}`.
  `texts` ← the input strings (always the array form per §3's "always a list"; the multimodal `inputs` /
  `images` form is out of scope — see *Out of scope*). The response
  `{"id": str, "embeddings": {"float": [[float, …], …]}, "texts": [str], "meta": {"billed_units": {"input_tokens": int}}}`
  maps onto 0059's shapes: `embeddings.float` → the `EmbeddingResponse` vectors **in input order**;
  `meta.billed_units.input_tokens` → `EmbeddingUsage.input_tokens`; top-level `id` →
  `EmbeddingResponse.response_id` (pinning, for Cohere, the per-vendor `response_id` source 0059 left
  position-agnostic). Cohere's embed response does not echo a model field, so `EmbeddingResponse.model`
  is the bound model identifier. The §4 cross-impl invariants (one vector per input, input-order keying,
  uniform dimensionality) are enforced against `embeddings.float`.
- **`input_type` realization (mandatory wire field).** Cohere v2 `/v2/embed` **requires** `input_type`,
  so unlike §8.1 / §8.2 (where an absent `input_type` omits the wire field) and §8.3 (symmetric no-op),
  this mapping MUST always send a value. It recognizes the **closed `input_type` set** (`query` /
  `document`, per 0078's treatment): `query` → `search_query`, `document` → `search_document`. **An absent
  `input_type` MUST map to `search_document`** — the conventional default for bulk embedding (storing
  document vectors is the dominant case, and the wire requires a value). An unrecognized OA `input_type`
  value is a pre-send `provider_invalid_request` (§7). Cohere's other `input_type` values
  (`classification` / `clustering` / `image`) are reached via the extras-pass-through bag, not OA's
  `input_type` (widening `input_type`'s normative value space is a protocol-level (0077) change, deferred
  until a consumer needs it).
- **`output_dimension` (Matryoshka).** `EmbeddingRuntimeConfig.dimensions` → Cohere's **`output_dimension`**
  (Cohere's name for the field; supported on the models that expose Matryoshka truncation) when set;
  omitted otherwise (Cohere's model default applies).
- **`embedding_types` / `truncate`.** The mapping requests `embedding_types: ["float"]` and consumes
  `embeddings.float`; other precisions ride the extras bag. It sends `truncate: "NONE"` so an
  over-length input **errors** (surfacing `provider_invalid_request` per §7) rather than being silently
  truncated — the §8.2 Jina embed fail-loud posture (and the point where §8.4's embed half diverges from
  its rerank half, which has no fail-loud option).
- **Mandatory batch chunking (96-input cap).** Cohere `/v2/embed` accepts at most **96 inputs per
  request**. When `len(input)` exceeds 96, the mapping MUST split the inputs into consecutive ≤96 chunks,
  issue one `/v2/embed` request per chunk (same `model` / `input_type` / `embedding_types` / `truncate`),
  and stitch: concatenate the per-chunk `embeddings.float` arrays **in input order** and sum
  `meta.billed_units.input_tokens` across chunks into `EmbeddingUsage.input_tokens`. This is valid
  because each embedding is computed independently of the others in its batch — the §8.1 TEI
  chunk-and-stitch argument, applied here to a **fixed vendor cap** (96) rather than TEI's
  construction-configured `chunk_size`. A mapping MUST NOT silently send an over-cap request; chunking is
  required, not optional. `EmbeddingResponse.response_id` is the first chunk's `id` (a single-request
  call uses that request's `id`); the §4 one-vector-per-input and uniform-dimensionality invariants are
  enforced against the stitched result. (A general §8 chunking rule across all embedding mappings is left
  as an open question — see *Open questions*.)
- **Errors.** Cohere HTTP failures map to the §7 categories per the shared enumeration, identical to the
  rerank half: `401` → `provider_authentication`; `429` → `provider_rate_limit`; `5xx` →
  `provider_unavailable`; unknown model (`404`) → `provider_invalid_model`; malformed / over-length
  request (`400`) → `provider_invalid_request`; malformed response → `provider_invalid_response`.
  (Cohere uses `400` for an invalid body, not the `422` Jina §8.2 returns — verified against the Cohere
  errors reference.)

## Conformance test impact

New fixtures under `spec/retrieval-provider/conformance/` (numbers assigned at Accept; appended after the
0090 Cohere-rerank wire set). Separate wire fixtures capturing the byte-level request
(`expected_wire_request`) and the v2 response shape, mirroring the 0079 / 0090 precedent and the §8.2
Jina embed fixtures:

- **Cohere `/v2/embed` mapping** — request carries `Authorization: Bearer`, `model`, `texts` (string
  array), `embedding_types: ["float"]`, `truncate: "NONE"`; the response `embeddings.float` assembles to
  vectors in input order; `meta.billed_units.input_tokens` → `EmbeddingUsage.input_tokens`; top-level
  `id` → `response_id`. Asserts the §4 one-vector-per-input and uniform-dimensionality invariants.
- **`input_type` → Cohere wire (incl. the mandatory-default)** — `input_type="query"` ⇒ wire
  `input_type="search_query"`; `"document"` ⇒ `"search_document"`; **absent ⇒ `"search_document"`** (the
  mandatory-field default — the case no other embed mapping has, since this wire cannot omit the field).
- **Unrecognized `input_type` rejected pre-send** — an OA `input_type` outside the closed `query` /
  `document` set raises `provider_invalid_request` before any wire request (the §8.2 closed-set
  behavior).
- **`output_dimension` passthrough** — `EmbeddingRuntimeConfig.dimensions` → wire `output_dimension`;
  absent ⇒ omitted.
- **`truncate: "NONE"` fail-loud** — an over-length input surfaces `provider_invalid_request` rather than
  a silently truncated vector.
- **>96-input chunk-and-stitch** — an `embed()` call with more than 96 inputs issues multiple `/v2/embed`
  requests (consecutive ≤96 chunks), and the stitched response carries one vector per input **in input
  order** with `EmbeddingUsage.input_tokens` summed across chunks. Asserts the over-cap request is
  chunked, not sent whole.

## Versioning

**MINOR bump** (pre-1.0), additive only: extends §8.4 with a new endpoint; no protocol surface changes
(the §8 section, the embedding shapes, and `input_type` are all prior work), no renumber. The
reconciliation of 0090's "rerank-only" sentence and the §11 deferred list are stale-text corrections
with no behavioral effect. The reference implementation gains a Cohere embeddings provider (HTTP client +
API-key auth + the `input_type` realization). Tentative spec version target deferred to Accept (sequenced
**after 0090**, since §8.4 must exist first).

## Alternatives considered

1. **A separate §8.5 Cohere-embeddings section instead of extending §8.4.** Reject — §8.4 is named for
   the vendor (Cohere), not the endpoint, exactly as §8.2 Jina covers both of Jina's endpoints in one
   section. A second Cohere-named section would fragment the vendor's wire mapping. The endpoint lands as
   an extension of the existing §8.4.
2. **Error when `input_type` is absent (force the caller to set it).** Reject — Cohere's wire requires a
   value, but erroring on absent would break composability with graphs that embed without specifying a
   query/document role, and would make the Cohere embed provider uniquely fragile among the embedding
   mappings. A defined default (`search_document`) keeps the call working; callers embedding queries set
   `input_type="query"` as they would for any asymmetric model.
3. **Default absent `input_type` to a neutral / symmetric value.** Reject — Cohere v2 `/v2/embed` has no
   symmetric `input_type`; every allowed value is role-specific. `search_document` is the closest to a
   neutral default (bulk vector storage) and the dominant use case; there is no truly symmetric option to
   choose.
4. **Bundle embed into 0090 (one Cohere proposal).** Reject (retroactively) — 0090 shipped rerank first
   to unblock 0060's reference reranker, deliberately scoping itself rerank-only and naming the embed
   wire a separate future mapping. This proposal is that mapping; splitting let 0090 land clean and lets
   the mandatory-`input_type` design surface get its own treatment here.
5. **Map `dimensions` via the extras bag rather than the declared field.** Reject — `output_dimension` is
   Cohere's name for the same Matryoshka knob 0078 / 0079 map from `EmbeddingRuntimeConfig.dimensions`;
   routing it through the declared field keeps the cross-vendor `dimensions` contract intact.
6. **Map to Cohere v1 (`/v1/embed`).** Reject — v2 is current; v2's required `input_type` and the
   type-keyed `embeddings` object are the forward-looking shape, consistent with the v2 rerank half
   (0090).
7. **Use the `inputs` (multimodal) request form.** Reject — 0059 is text + dense float vectors; the
   `texts` form is the text-only interface. Multimodal `inputs` / `images` are out of scope.

## Open questions

**Open — awaiting a maintainer ruling (at Accept):**

- **The absent-`input_type` default.** The wire requires a value, so the mapping must pick one for the
  absent OA case. **Recommendation: `search_document`** (bulk-indexing is the dominant embedding case;
  Alternatives 2 / 3 reject erroring and a neutral value). A fourth option — a **construction-bound
  default `input_type`** (the operator sets the per-instance fallback, with precedent in TEI's
  construction-bound `input_type → prompt_name` map) — trades wire simplicity for construction surface;
  the recommendation is the fixed `search_document` default, but the ruling may prefer the configurable
  form. The Conformance fixtures are written to the `search_document` default; a different ruling changes
  the absent-case fixture and the §8.4 `input_type` paragraph.
- **A general §8 embedding-mapping chunking rule (cross-mapping).** 0091 specs chunk-and-stitch for
  Cohere's fixed 96-input cap, but the accepted embed mappings (§8.1 TEI `/embed`, §8.2 Jina, §8.3
  OpenAI) do not address their own per-call input caps at all — so the question *"must every embedding
  mapping chunk-and-stitch when input exceeds the vendor per-call cap, or error?"* is a cross-mapping one
  that a general §8 rule (or a follow-on touching each mapping) would settle. 0091 closes only Cohere's
  instance; the general rule is **out of scope here** and tracked in `docs/open-questions.md` as a
  candidate for a follow-on proposal.

**Resolved (during drafting / review):**

- **Response embeddings keyed by type.** RESOLVED: request `embedding_types: ["float"]`, consume
  `embeddings.float` in input order; other precisions out of scope.
- **`embedding_types` sent explicitly.** RESOLVED: the mapping sends `embedding_types: ["float"]` rather
  than relying on Cohere's `["float"]` wire default, so the type-keyed response is guaranteed to carry the
  `embeddings.float` key the mapping reads (the §8.2 "send `return_documents` explicitly" posture).
- **`texts` vs `inputs`.** RESOLVED: `texts` (text-only); multimodal `inputs` / `images` out of scope.
- **Fail-loud.** RESOLVED: send `truncate: "NONE"` (the §8.2 Jina embed posture); `/v2/embed` exposes
  the option that `/v2/rerank` did not.
- **Error-status-code mapping.** RESOLVED: verified against the Cohere errors reference (the same codes
  as the rerank half) — `401`/`404`/`400`/`429`/`5xx`; Cohere does not use `422`. The over-length case is
  asserted by the §7 **category** (`provider_invalid_request`), not a pinned HTTP code.
- **Per-vendor `response_id` and `model` source.** RESOLVED: top-level `id` → `response_id`; Cohere's
  embed response echoes no model field, so `EmbeddingResponse.model` is the bound model identifier.

**Deferred to Accept (alignment, not design):**

- **§8.4 reconciliation** — at Accept, update 0090's "rerank-only — no `EmbeddingProvider` counterpart
  in this mapping (a Cohere embeddings wire is a separate future mapping)" sentence in §8.4, now
  satisfied, and generalize the §8.4 construction paragraph to both endpoints.
- **§11 *Out of scope* reconciliation** — remove Cohere embedding from the per-vendor deferred list
  (alongside the Cohere-rerank and stale Jina / OpenAI corrections 0090 already flags).
- **`gen_ai.system`** — confirm `"cohere"` (the §8.4 rerank value) carries to the embed span when writing
  the extension.

## Out of scope

- **Multimodal embeddings (`inputs` / `images`).** Cohere v2 embeds images and multimodal inputs; 0059 is
  text + dense float vectors only.
- **Non-float embedding types (`int8` / `uint8` / `binary` / `ubinary` / `base64`).** Ride the
  extras-pass-through bag; `float` is the declared dense-vector output.
- **`max_tokens`, `priority`, and other Cohere-specific knobs as declared protocol fields.** Extras bag.
- **Cohere `input_type` values beyond `query` / `document`** (`classification` / `clustering` / `image`).
  Reached via the extras bag; widening `input_type`'s value space is a protocol-level (0077) change.
- **Cohere v1 (`/v1/embed`).** v2 only (see Alternatives 6).
- **Other embedding vendors (Voyage AI).** Remain deferred (retrieval-provider §11 *Out of scope*).
