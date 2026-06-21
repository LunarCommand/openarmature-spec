# 0077: TEI Retrieval-Provider Wire Mapping + Asymmetric Query/Document Embedding

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-21
- **Accepted:**
- **Targets:** spec/retrieval-provider/spec.md (§2 *Concepts* + §3 *EmbeddingProvider protocol* — the *Embedding runtime config* gains a declared `input_type` field; new **§8 Wire-format mappings** with **§8.1 TEI** covering both of TEI's `/embed` and `/rerank` surfaces — served as separate per-model instances — analogous to llm-provider §8.1 / §8.2 / §8.3 — this is the first concrete retrieval-provider wire mapping; the section restructure renumbers existing §8 *Determinism* → §9, §9 *Cross-spec touchpoints* → §10, §10 *Out of scope* → §11, and the §10/§11 out-of-scope wire-mapping deferral drops its TEI entry, now landed); plus new conformance fixtures under `spec/retrieval-provider/conformance/`. No graph-engine change: `input_type` flows into the existing `EmbeddingEvent.request_params` (graph-engine §6) absence-is-meaningfully, like `dimensions`. Minor observability touch: `input_type` is a request-side embedding runtime-config field, surfaced on the §5.5.8 embedding span the same way the existing request-params family is (no new attribute family).
- **Related:** 0059 (retrieval-provider embedding protocol — the `embed()` / `EmbeddingRuntimeConfig` surface this extends, and the deferred-all-wire-mappings posture this begins to fill), 0060 (rerank protocol — the `RerankProvider` contract the TEI `/rerank` mapping realizes, including the `results` sort + valid-index invariants), 0006 / 0037 / 0038 (llm-provider §8.X wire-mapping pattern — the per-vendor / per-runtime mapping precedent this mirrors for retrieval-provider)
- **Supersedes:**

## Summary

Driven by a concrete self-hosted-TEI + BGE RAG consumer (running BGE embeddings query- and
document-side plus a BGE cross-encoder reranker, all on HuggingFace Text Embeddings Inference), this
proposal lands two things — the **first concrete retrieval-provider wire mapping**, plus the one
embedding-protocol gap that self-hosted setup exposes:

1. **Asymmetric query/document embedding — a cross-vendor `input_type` knob.** Retrieval embedders
   are *asymmetric*: the query side needs different treatment from the document side. For BGE / E5 /
   GTE / Instructor that is a query-side instruction prefix the document side must NOT get; for the
   hosted vendors it is a wire parameter (Cohere `input_type`, Voyage `input_type`, Jina `task`).
   `EmbeddingProvider.embed()` today is symmetric — there is no way to say "this is a query
   embedding," so every consumer re-implements the distinction by hand and the failure mode is
   **silent**: mistreated query vectors land in the wrong region of the space and recall degrades
   with no error. This adds a declared `input_type` field (`"query"` / `"document"`, extensible) on
   `EmbeddingRuntimeConfig`; the provider maps it to the model-appropriate treatment. Absent ⇒ the
   v0.54.0 symmetric behavior, exactly (backward-compatible).

2. **The TEI wire-format mapping (§8.1) — both of TEI's surfaces, as separate per-model instances.**
   TEI is a self-hosted serving runtime (HuggingFace `text-embeddings-inference`) that hosts **one
   model per instance**; an embedding model and a cross-encoder reranker are different model families,
   so they run as **two separate TEI deployments** (two `base_url`s). The mapping covers both surfaces
   as two distinct providers — a TEI `EmbeddingProvider` (`/embed`, bound to the embedding instance)
   and a TEI `RerankProvider` (`/rerank`, bound to the reranker instance), each binding its own
   `base_url`. It pins: the `/embed` shape + the `input_type` realization via TEI's native server-side
   `prompt_name` (client-side prefix fallback); the `/rerank` shape (`{query, texts}` →
   `[{index, score}]`, mapping cleanly onto 0060's `documents` / `results`, `return_documents` →
   `return_text`); **mandatory client-side batch chunking** for rerank (TEI caps
   `max-client-batch-size`, default 32 — a pool larger than the cap MUST be split into per-chunk
   requests and the scores stitched back with a global re-sort, valid because a cross-encoder scores
   each `(query, document)` pair independently); and `truncate: false` (TEI's default) so an
   over-length pair errors loudly rather than truncating silently.

Together these "fully support TEI" — closing the two-stage RAG loop (embed → rerank) across the
self-hosted TEI deployments (an embedding instance + a reranker instance) — and make the embedding
protocol correct for the whole asymmetric-retrieval-embedder family,
not just TEI.

## Motivation

**The asymmetric-embedding gap is a silent-correctness bug, not polish.** Most modern retrieval
embedders are trained with distinct query and document representations. BGE prepends a query
instruction ("Represent this sentence for searching relevant passages: …") on the query side only;
E5 uses `query:` / `passage:` prefixes; Cohere / Voyage take an `input_type`; Jina takes a `task`.
Embed a query as if it were a document and you get a syntactically valid vector that simply retrieves
worse — **no exception, no signal, just lower recall**. A symmetric `embed()` gives the caller no
place to express the distinction, so each consumer hand-rolls it and silently diverges. A declared
`input_type` makes the contract explicit and lets the provider apply the right treatment per model.

**Cross-vendor, not TEI-specific.** `input_type` is the embedding landscape's lingua franca —
`input_type` (Cohere, Voyage), `task` (Jina), query/passage prefixes (BGE/E5/GTE). So the knob belongs
on the protocol (one declared field), realized per wire mapping: TEI prepends a prefix client-side;
the hosted vendors pass a wire parameter. This proposal lands the protocol field + the TEI
realization; 0078 (Jina) and later Cohere/Voyage mappings realize the same field on their wire.

**TEI is the self-hosted retrieval runtime, and its batch cap is a hard wall.** Per the
embedding/rerank provider-landscape framing in 0059 / 0060, TEI serves both embedding and rerank
models for teams that self-host — one model per instance, so a separate TEI deployment for each
(data-residency, cost, model choice). Its `max-client-batch-size` (default 32)
is enforced server-side: a realistic rerank candidate pool (hundreds of documents) **hard-fails**
unless the client splits it into ≤cap requests and stitches the per-pair scores. Baking the
chunk-and-stitch into the provider — rather than leaving every consumer to rediscover it — is the
difference between a usable TEI rerank provider and one that breaks on the first real query. This is
the load-bearing piece the mapping must specify.

**First retrieval-provider wire mapping.** 0059 and 0060 deferred *all* wire mappings (the protocol
is runtime-agnostic by design). This is the first one to land, establishing the
retrieval-provider §8 *Wire-format mappings* section that the hosted-vendor mappings (Jina, Cohere,
Voyage) extend, exactly as llm-provider §8.1 (OpenAI-compatible) anchored that catalog.

## Proposed change

### 1. `input_type` on the embedding protocol (§2 *Concepts* + §3 *EmbeddingProvider protocol*)

**§2 — extend the *Embedding runtime config* concept** to declare `input_type` alongside `dimensions`:

- **`input_type`** — optional string, default absent. Declares what the embedded text is *for*, so a
  provider bound to an asymmetric model applies the model-appropriate treatment. Normative value
  space in v1: `"query"` and `"document"`. The field is an **extensible string** (not a closed enum)
  — additional well-known values (`"classification"`, `"clustering"`, …) MAY be recognized by
  mappings whose backend supports them, added by follow-on proposals when a consumer surfaces; an
  unrecognized value is a `provider_invalid_request` (§7) at the pre-send validation layer of a
  mapping that declares a closed set, or passed through for mappings that accept arbitrary types.
  **Absent ⇒ symmetric embedding** — the exact v0.54.0 behavior; a symmetric model (e.g. OpenAI
  `text-embedding-3`) ignores it. Free-form per-model instruction overrides remain available through
  the existing extras-pass-through bag (no second declared field).

**§3 — `embed()` / `EmbeddingRuntimeConfig`:** `input_type` is supplied via `config`
(`EmbeddingRuntimeConfig`); the `embed(input, *, config=None)` signature is unchanged. The provider
applies the model-appropriate query/document treatment per its §8.X wire mapping. `input_type` is a
request-side parameter; it flows into `EmbeddingEvent.request_params` (graph-engine §6) with the same
absence-is-meaningful semantics as `dimensions`, and is surfaced on the §5.5.8 embedding span through
the existing request-parameter family (no new OTel attribute).

### 2. New **§8 Wire-format mappings** + **§8.1 TEI** (section restructure)

A new top-level *Wire-format mappings* section, placed after §7 *Error semantics* (mirroring
llm-provider §8's placement after its error section). The restructure:

| Current section | Post-0077 section | Change |
|---|---|---|
| §7 Error semantics | §7 Error semantics | Unchanged |
| — | **§8 Wire-format mappings** (intro + **§8.1 TEI**) | NEW |
| §8 Determinism | §9 Determinism | Renumbered |
| §9 Cross-spec touchpoints | §10 Cross-spec touchpoints | Renumbered |
| §10 Out of scope | §11 Out of scope | Renumbered; TEI dropped from the wire-mapping deferral (now landed) |

Cross-references to retrieval-provider §8 / §9 / §10 from other specs and fixtures update to §9 / §10 /
§11 at Accept (enumerated in *Conformance test impact*).

**§8 intro** — wire mappings are per-vendor / per-runtime realizations of the runtime-agnostic
`EmbeddingProvider` / `RerankProvider` contracts (§3 / §5), the retrieval-provider analogue of
llm-provider §8. Each mapping pins the wire shapes, the construction parameters (e.g. `base_url`), and
the per-mapping realization of cross-vendor knobs (`input_type`).

**§8.1 TEI** (HuggingFace Text Embeddings Inference — a self-hosted serving runtime; `gen_ai.system`
identifier `"tei"` per the observability §5.5.8 / §5.5.13 "identify the wire surface, not the model
developer" convention). The `/embed` + `/rerank` wire shapes below were **verified against the TEI
OpenAPI on 2026-06-21**; the verified versions are recorded in `docs/compatibility.md` at Accept:

- **Construction (two separate instances).** TEI hosts one model per instance, and embedding models
  and cross-encoder rerankers are different families — so a TEI `EmbeddingProvider` and a TEI
  `RerankProvider` are **distinct provider instances against distinct TEI deployments**, each binding
  its own `base_url` (§3 / §5 per-instance binding):
  - the **TEI `EmbeddingProvider`** binds `base_url` (the embedding instance) + the bound model + an
    **`input_type` → `prompt_name` map** (e.g. `{query: "query", document: "passage"}`) realizing
    asymmetric embedding via TEI's native server-side prompts, with OPTIONAL client-side
    `query_prefix` / `document_prefix` strings as the fallback for models without configured prompts;
  - the **TEI `RerankProvider`** binds `base_url` (the reranker instance) + the bound model +
    `chunk_size` (the rerank client-batch chunk size, default `32` — see *Mandatory rerank batch
    chunking*).

  The spec does NOT enumerate per-model prefixes (model-specific, a moving target) — they are
  operator-supplied at construction.
- **`/embed`** — `POST {base_url}/embed` with `{"inputs": [str]}` (TEI accepts a string or array; the
  mapping always sends the array form per §3's "always a list"); `EmbeddingRuntimeConfig.dimensions`
  maps to TEI's `dimensions` field when set. Response is the vector array, in input order.
  **`input_type` realization:** the mapping sends TEI's native **`prompt_name`** field, looked up from
  the construction `input_type → prompt_name` map, so TEI applies the model's configured
  query/document prompt **server-side** (the idiomatic path — TEI models carry named prompts in their
  config). For a model without configured prompts, the mapping MAY instead prepend the
  construction-supplied `query_prefix` / `document_prefix` **client-side**. Either way, `input_type`
  absent ⇒ no prompt and no prefix (the symmetric / v0.54.0 path).
- **`/rerank`** — `POST {base_url}/rerank` with `{"query": str, "texts": [str], "truncate": false, "return_text": <bool>}`.
  TEI's `texts: [str]` maps directly onto 0060's `documents: list[str]` (no per-document object
  wrapping); **0060's `return_documents` → TEI's `return_text`** (default `false`), surfacing the
  echoed text on `ScoredDocument.document`. Response `[{"index": int, "score": float, "text"?: str}]`
  maps onto 0060's `results` (`index` → `ScoredDocument.index`, `score` → `relevance_score`,
  `text` → `document`); scores are normalized by default (`raw_scores: false`), the scale model-specific
  (0060 pins none). **TEI does not guarantee response sort order** (its OpenAPI declares none), so the
  mapping sorts per 0060's existing "sort if the provider didn't" invariant — subsumed by the
  chunk-and-stitch global re-sort below.
- **Mandatory rerank batch chunking.** TEI enforces `max-client-batch-size` (server-configured,
  default 32). When `len(documents)` exceeds the instance's `chunk_size`, the mapping MUST split the
  documents into consecutive ≤`chunk_size` chunks, issue one `/rerank` request per chunk (same
  `query`), and **stitch the results**: re-base each chunk's `index` to its absolute position in the
  original `documents` list, concatenate all `(index, score)` pairs, then apply 0060's contract — sort
  by `score` descending and honor `top_k`. Valid because a cross-encoder scores each
  `(query, document)` pair independently of the others in its batch. `chunk_size` is a **construction
  parameter**, default `32` (TEI's documented default; an operator who lowered `--max-client-batch-size`
  sets it to match; an impl MAY auto-detect from TEI's `/info`). A mapping that does not chunk MUST NOT
  silently send an over-cap request (it hard-fails); chunking is required, not optional.
- **`truncate: false` (fail-loud).** TEI's `truncate` defaults to `false`, so an over-length
  `(query, document)` pair (or `/embed` input) **errors rather than being silently truncated** (model
  context caps vary). The mapping sends `truncate: false` explicitly (leaving TEI's
  `truncation_direction` default, `Right`); the resulting TEI error (HTTP 413 / 422) maps to
  `provider_invalid_request` per §7.
- **Errors** — TEI HTTP / transport failures map to the §7 categories per the shared enumeration
  (connection / 5xx → `provider_unavailable`; unknown model → `provider_invalid_model`; over-length /
  malformed request (413 / 422) → `provider_invalid_request`; malformed response →
  `provider_invalid_response`).

### 3. §11 *Out of scope* — drop the TEI wire-mapping deferral

The renumbered §11 *Out of scope* removes TEI from the "Per-vendor and per-runtime wire-format
mappings" deferral item (now landed); the hosted-vendor mappings (Cohere, Voyage, and Jina via 0078)
remain deferred there.

## Conformance test impact

New fixtures under `spec/retrieval-provider/conformance/` (numbers assigned at Accept; appended after
the existing rerank set 006–012):

- **`input_type` on embed** — `embed(config={input_type: "query"})` vs `input_type: "document"` vs
  absent: asserts the value reaches `EmbeddingEvent.request_params` and (TEI realization) that the
  query prefix is prepended for `"query"` and not for `"document"` / absent. Backward-compat case:
  absent `input_type` ⇒ byte-identical to the pre-0077 symmetric path.
- **TEI `/rerank` within a single batch** — pool ≤ cap: one `/rerank` request; assembled `results`
  match 0060's sort + valid-index invariants.
- **TEI `/rerank` chunk-and-stitch** — pool > cap (e.g. cap 4, 9 documents): asserts the mapping
  issues ⌈9/4⌉ = 3 requests, re-bases each chunk's `index` to the absolute input position, merges +
  globally sorts by score descending, and honors `top_k`. **Load-bearing** — locks the chunking
  contract.
- **TEI `truncate: false` fail-loud** — an over-length pair surfaces `provider_invalid_request`, not
  a silently truncated score.
- **TEI `/embed`** — `{inputs: [...]}` request shape, input-order-preserved response.

### Cross-reference updates at Accept

The §8 → §9 / §9 → §10 / §10 → §11 renumber shifts references to retrieval-provider *Determinism* /
*Cross-spec touchpoints* / *Out of scope*. Sweep `spec/` + `docs/` for `retrieval-provider §8` /
`§9` / `§10` and update; the embedding/rerank §7 *Error semantics* reference is unchanged.

## Versioning

**MINOR bump** (pre-1.0). Additive at every surface:

- `input_type` is an optional `EmbeddingRuntimeConfig` field defaulting to absent — existing callers
  and symmetric models are byte-for-byte unaffected.
- The TEI mapping is a new §8.1 section; the runtime-agnostic protocol is unchanged.
- The §8–§10 → §9–§11 renumber is internal to the retrieval-provider spec (cross-references reconciled
  in the same Accept PR).

Not a textual-only proposal: the reference implementation gains a real TEI embed + rerank provider
(HTTP client, the chunk-and-stitch, the prefix realization). Tentative spec version target deferred to
Accept.

## Alternatives considered

1. **`is_query: bool` instead of `input_type`.** Reject — a strict binary subset of `input_type` with
   no room for the other well-known types (Cohere `classification` / `clustering`) and an awkward
   name. `input_type="query"` / `"document"` covers the same case and extends cleanly.
2. **A free-form `instruction` / `prompt_name` declared field.** Reject as a *declared* field — it
   pushes model-specific knowledge to the caller, and the existing `EmbeddingRuntimeConfig`
   extras-pass-through bag already serves the free-form-override escape hatch (e.g. an Instructor-style
   custom instruction). `input_type` (declared, semantic) + extras (escape hatch) covers the space
   without a second declared field.
3. **`input_type` via the extras bag only (no declared field).** Reject — a correctness-critical,
   silent-failure-prone, cross-vendor concern deserves a typed, discoverable, consistently-named
   declared field, not a per-mapping extras-key convention each consumer must rediscover.
4. **A separate proposal for `input_type`, with TEI as a pure wire mapping.** Reasonable, and cleaner
   on the protocol-vs-mapping seam — but the TEI consumer is precisely what surfaces the gap, and
   "fully support TEI" requires the knob (BGE query embeddings are wrong without it), so landing them
   together keeps the roadmap to the two planned wire-mapping proposals (0077 TEI, 0078 Jina). The
   `input_type` text lives in the protocol §2 / §3 (general), not under §8.1 — so the coupling is
   editorial, not architectural.
5. **Leave rerank batch chunking to the consumer.** Reject — TEI's cap is a hard server-side wall;
   an un-chunked provider hard-fails on any realistic pool. Baking chunk-and-stitch into the mapping
   is the difference between a usable provider and one that breaks immediately.
6. **A dedicated `tei-provider` capability.** Reject — TEI is a wire mapping of the existing
   `EmbeddingProvider` / `RerankProvider` contracts, exactly as vLLM is served through the
   OpenAI-compatible llm-provider §8.1 mapping. No new capability.

## Open questions

None remaining at draft time. The three surfaced during drafting are resolved in the §8.1 text above
(collected here for retrieval).

**Resolved at Draft:**

- **Per-model prefix sourcing** — realize `input_type` via TEI's native **`prompt_name`**
  (server-side, idiomatic; construction binds an `input_type → prompt_name` map), with
  construction-supplied client-side `query_prefix` / `document_prefix` as the fallback for models
  lacking configured prompts. The spec does NOT own a model→prefix table (model-specific, a moving
  target).
- **TEI `/rerank` response + `truncate`** — **verified against the TEI OpenAPI (2026-06-21):** request
  `{query, texts, truncate (default false), return_text (default false), raw_scores (default false),
  truncation_direction (default Right)}`; response `[{index, score, text?}]` with **no guaranteed
  sort** (the mapping sorts per 0060). `truncate` defaults `false` ⇒ fail-loud is TEI's default.
  Cross-mappings: `return_documents` → `return_text`, `dimensions` → `dimensions`. To be recorded in
  `docs/compatibility.md` at Accept (re-confirmed there per the verification discipline).
- **Chunk-size default** — a construction parameter `chunk_size`, default `32` (TEI's documented
  `max-client-batch-size` default); an impl MAY auto-detect from TEI's `/info`.

## Out of scope

- **Hosted-vendor embedding/rerank wire mappings** — Cohere, Voyage, and Jina (the latter is 0078).
  Each realizes `input_type` on its own wire (`input_type` / `task`) and pins its own response shape.
- **Non-retrieval `input_type` values** — `classification`, `clustering`, etc. Added by follow-ons
  when a consumer needs them; v1 pins `query` / `document` (the retrieval case with a consumer).
- **Multi-modal embedding / rerank** — image/audio documents. Text-only, per 0059 / 0060.
- **TEI `/embed` sparse / late-interaction outputs** (SPLADE, ColBERT-style) — dense vectors only in
  v1; sparse/multi-vector retrieval is a separate concern.
- **Streaming** — embedding / rerank streaming remains out of scope per 0060.
