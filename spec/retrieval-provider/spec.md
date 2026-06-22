# Retrieval Provider

Canonical behavioral specification for the OpenArmature retrieval-provider abstraction.

- **Capability:** retrieval-provider
- **Introduced:** spec version 0.54.0
- **History:**
  - created by [proposal 0059](../../proposals/0059-retrieval-provider-embedding.md)
  - rerank protocol added by [proposal 0060](../../proposals/0060-retrieval-provider-rerank.md)

This specification is language-agnostic. Each implementation (Python, TypeScript, …) maps its own idioms
onto the behavioral contract described here. Conformance is verified by the fixtures under `conformance/`.

Normative keywords (MUST, MUST NOT, SHOULD, MAY) are used per [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## 1. Purpose

The retrieval-provider capability is the home for retrieval-primitive provider operations that sit
alongside LLM completion. The first protocol surface this specification defines is **embedding** —
turning a list of input strings into a list of vectors via an `EmbeddingProvider`. A sibling
`RerankProvider` protocol (§5) re-scores a list of candidate documents against a query, returning
them sorted by relevance — the second retrieval-primitive surface on the same capability.

Retrieval-provider is a sibling capability to `llm-provider` (per proposal 0006),
not a subtype of it. Embedding and LLM completion both bind per-instance to a model identifier per
the llm-provider §5 contract, but embedding model identifiers (`text-embedding-3-small`,
`voyage-3`, `embed-multilingual-v3.0`, etc.) live in disjoint namespaces from completion model
identifiers (`gpt-4o-mini`, `claude-3-5-sonnet`, etc.). A single Provider abstraction bundling both
surfaces would either contradict the per-model-binding contract OR carve a different contract shape
for the same protocol — both bad. Separate protocols preserve per-model-binding while opening a
path to observable embedding calls.

Retrieval-provider is one of a planned family of `<domain>-provider` capabilities (`llm-provider`,
`retrieval-provider`, plus future siblings as downstream demand surfaces). Each domain capability
covers related-shape provider operations under a narrow protocol surface; new domains land as new
capabilities rather than as extensions to existing ones. This keeps per-capability protocol surface
narrow and per-domain evolution independent.

The substrate is intentionally narrow, matching llm-provider's posture:

- An `EmbeddingProvider` is **stateless**. It does not cache vectors; the caller passes the full
  input list on every call.
- An `EmbeddingProvider` does **not** handle retry, rate limiting, fallback, or routing. Those are
  pipeline-utilities concerns and compose above the provider via middleware.
- An `EmbeddingProvider` is **bound to a single model identifier**. Switching models means
  constructing a new provider, not passing a different argument per call.

**Transparency.** Per charter §3.1 principle 8 ("Transparency over abstraction"), the embedding
abstraction surfaces a normalized shape — `EmbeddingResponse`, `EmbeddingUsage` — without hiding
what the underlying provider returned. The `EmbeddingResponse.raw` field carries the parsed provider
response verbatim alongside the normalized fields, and the error categories preserve the underlying
provider exception as cause.

## 2. Concepts

**RetrievalProvider.** The umbrella term covering both `EmbeddingProvider` and `RerankProvider`. Not
a concrete protocol itself; used as the capability-level descriptor when discussing cross-protocol
concerns (observability, error semantics, per-model binding).

**EmbeddingProvider.** An object that, given a sequence of input strings, returns a sequence of
vectors wrapped in an `EmbeddingResponse`. Bound to a specific embedding model identifier per
instance.

**EmbeddingResponse.** The result of an `embed()` call: the vectors, the model identifier, usage
information, and (when present) the provider-returned request identifier and the parsed raw
response.

**EmbeddingUsage.** A usage record carrying `input_tokens` only — embedding has no output tokens
(vectors aren't tokens).

**Embedding runtime config.** A `RuntimeConfig`-shaped record (parallel to llm-provider §6) carrying
embedding-specific caller-supplied request parameters: an optional `dimensions` field (for callers
controlling output vector size on providers that support it), an optional **`input_type`** field, and
the extras-pass-through bag for vendor-specific knobs. `input_type` (`"query"` / `"document"`, an
extensible string) declares what the embedded text is *for*, so a provider bound to an asymmetric model
applies the model-appropriate query/document treatment per its §8 wire mapping; **absent ⇒ symmetric
embedding** (a symmetric model ignores it). Additional well-known values (`"classification"`,
`"clustering"`, …) MAY be recognized by mappings whose backend supports them; an unrecognized value is
`provider_invalid_request` (§7) at a mapping that declares a closed set, or passed through by a mapping
that accepts arbitrary types. Free-form per-model instruction overrides ride the extras-pass-through
bag (no second declared field).

**RerankProvider.** An object that, given a query string and a list of candidate documents, returns
the documents sorted by query-relevance with provider-specific scores. Bound to a specific rerank
model identifier per instance.

**RerankResponse.** The result of a `rerank()` call: the sorted scored documents, the model
identifier, usage information, and (when present) the provider-returned response identifier and the
parsed raw response.

**RerankUsage.** A usage record with optional `search_units` and optional `input_tokens`, reflecting
the messy provider landscape where rerank pricing surfaces vary widely.

**ScoredDocument.** A single result entry carrying the document's original index in the input list,
the provider-assigned relevance score, and (optionally) an echo of the document text.

**Rerank runtime config.** A `RuntimeConfig`-shaped record (parallel to llm-provider §6) carrying
rerank-specific caller-supplied request parameters. Initially minimal: one declared field,
`return_documents` (boolean, default `False`), controlling whether the provider echoes document text
on each `ScoredDocument` in the response. The field name + default match the major rerank vendors'
wire-shape parameter (Cohere, Voyage AI, Jina AI all expose `return_documents` defaulting `False`);
per-vendor wire-format mappings pin the source-side translation where a vendor diverges. Plus the
extras-pass-through bag for vendor-specific knobs.

## 3. EmbeddingProvider protocol

The `EmbeddingProvider` protocol exposes two async operations.

### `ready()`

A no-argument async operation that verifies the provider can serve requests against the bound
model. Implementations MAY surface a hosted-provider authentication check, a local-model load
attempt, or a noop — whichever fits the backend. The operation:

- MUST be idempotent. Repeated `ready()` calls MUST NOT change observable provider state.
- MUST surface `provider_invalid_model` (per §7) if the bound embedding model is not recognized by
  the backend.
- MUST surface `provider_model_not_loaded` (per §7) if the bound model is recognized but not
  currently usable (e.g., a local model that requires explicit loading).
- MAY raise other §7 error categories (`provider_authentication`, `provider_unavailable`) when the
  underlying readiness check encounters those conditions.

### `embed(input, *, config=None)`

The embedding operation. Parameters:

| Parameter | Type | Description |
|---|---|---|
| `input` | list of strings | The input strings to embed. MUST be a list even for single-string callers (callers wrap as a one-element list). Matches `complete()`'s "always a list" message contract. |
| `config` | optional `EmbeddingRuntimeConfig` (keyword-only) | Caller-supplied embedding runtime config. Keyword-only (or per-language idiomatic equivalent that prevents positional confusion with `input`). |

Returns an `EmbeddingResponse` (§4).

The `embed()` operation:

- MUST be stateless. Repeated calls with the same `input` and `config` MUST NOT change observable
  provider state.
- MUST raise one of the §7 error categories on failure. The §7 enumeration is shared cross-
  capability with llm-provider §7; embedding-applicable subset documented in §7.
- MUST preserve input order in the response (the vector at index `i` MUST be the embedding of
  `input[i]`). Implementations MUST NOT permute vector position relative to input position.
- MUST NOT loop, retry, or fall back. Pipeline-utilities §6 middleware and per-call retry compose
  above the provider for those concerns.

**Query vs. document (`input_type`).** When the caller sets `EmbeddingRuntimeConfig.input_type` (§2),
the provider applies the model-appropriate query/document treatment per its §8 wire mapping.
`input_type` is a request-side parameter: it flows into `EmbeddingEvent.request_params` (graph-engine
§6) with the same absence-is-meaningful semantics as `dimensions`, and is surfaced on the embedding
span (observability §5.5.8) through the existing request-parameter family — no new attribute. Absent ⇒
the symmetric default.

### Per-instance model binding

Per-instance model binding follows the llm-provider §5 contract exactly. Implementations bind one
embedding model identifier per provider instance via a constructor parameter (or per-language
idiomatic equivalent). The bound identifier is visible to the observability layer (per observability §5.5) as the
`gen_ai.request.model` attribute on the embedding span.

## 4. EmbeddingResponse and EmbeddingUsage shapes

### EmbeddingResponse

| Field | Description |
|---|---|
| `vectors` | List of vectors (each a list of floats); one vector per input string in the order the inputs were supplied. The length of `vectors` MUST equal the length of `input`. |
| `model` | The model identifier the provider returned. MAY be a more specific identifier than the one the provider was bound against. |
| `usage` | An `EmbeddingUsage` record (defined below). |
| `response_id` | The provider-returned response identifier when present; null otherwise. Matches the OTel GenAI semconv `gen_ai.response.id` attribute (per observability §5.5.8) and the typed `EmbeddingEvent.response_id` field (per graph-engine §6). |
| `dimensions` | Int. The output vector dimensionality. MUST equal the length of each inner list in `vectors`. Derivable from `vectors[0]` but kept on the response for ergonomics and cross-vendor consistency. |
| `raw` | The parsed provider response, as a language-idiomatic representation of deserialized JSON (Python: `dict[str, Any]`; TypeScript: `Record<string, unknown>`). MUST be populated on every successful return. Parallel to llm-provider §6 `Response.raw`. |

### EmbeddingUsage

| Field | Description |
|---|---|
| `input_tokens` | Int. Tokens billed for the embedding call. Always reported (no `output_tokens` — vectors aren't tokens). |

### Cross-impl invariants

- Exactly one vector per input string (the length of `vectors` MUST match the length of `input`).
- Vector position is keyed by input order; implementations MUST NOT permute.
- All vectors in a single response have the same dimensionality. Implementations MUST verify this
  on the response and raise `provider_invalid_response` (§7) if violated.
- The `dimensions` field on the response MUST equal the dimensionality of each inner vector —
  cross-check invariant for adapters.
- Implementations MUST raise `provider_invalid_response` (§7) when the response carries a mismatched
  count of vectors vs. input strings.

## 5. RerankProvider protocol

The `RerankProvider` protocol exposes two async operations, mirroring `EmbeddingProvider` (§3) with
rerank-specific shapes.

### `ready()`

A no-argument async operation that verifies the provider can serve requests against the bound rerank
model. Same idempotency + error-surfacing contract as §3's `ready()`:

- MUST be idempotent. Repeated `ready()` calls MUST NOT change observable provider state.
- MUST surface `provider_invalid_model` (per §7) if the bound rerank model is not recognized by the
  backend.
- MUST surface `provider_model_not_loaded` (per §7) if the bound model is recognized but not
  currently usable.
- MAY raise other §7 error categories (`provider_authentication`, `provider_unavailable`) under the
  same conditions as §3's `ready()`.

### `rerank(query, documents, *, top_k=None, config=None)`

The rerank operation. Parameters:

| Parameter | Type | Description |
|---|---|---|
| `query` | string | The query string the documents are scored against. MUST be non-empty; an empty query raises `provider_invalid_request` (§7) at the pre-send validation layer. |
| `documents` | list of strings | The candidate documents to score against the query. MUST be a list (single-document callers wrap as a one-element list — matches the embedding protocol's "always a list" framing). MUST be non-empty; an empty document list raises `provider_invalid_request` (§7). |
| `top_k` | optional int (keyword-only) | The maximum number of results the caller wants returned. `None` means "all" (the provider MAY return up to `len(documents)` results). MUST be positive when supplied; zero or negative raises `provider_invalid_request` (§7). MAY exceed `len(documents)` — the provider returns at most `len(documents)` results regardless. |
| `config` | optional `RerankRuntimeConfig` (keyword-only) | Caller-supplied rerank runtime config. Keyword-only (or per-language idiomatic equivalent that prevents positional confusion). |

Returns a `RerankResponse` (§6).

The `rerank()` operation:

- MUST be stateless. Repeated calls with the same `query` / `documents` / `top_k` / `config` MUST NOT
  change observable provider state.
- MUST raise one of the §7 error categories on failure.
- MUST return results sorted by `relevance_score` descending (most relevant first).
- MUST preserve each result's `index` field as the position in the *input* `documents` list, so
  callers can map sorted results back to their original documents.
- MUST NOT loop, retry, or fall back. Pipeline-utilities §6 middleware and per-call retry compose
  above the provider.

### Per-instance model binding

Per-instance model binding follows the llm-provider §5 contract exactly, identical to §3's framing.
Implementations bind one rerank model identifier per provider instance via a constructor parameter
(or per-language idiomatic equivalent). The bound identifier is visible to the observability layer
(per observability §5.5) as the `gen_ai.request.model` attribute on the rerank span.

## 6. RerankResponse, RerankUsage, ScoredDocument shapes

### RerankResponse

| Field | Description |
|---|---|
| `results` | List of `ScoredDocument` entries sorted by `relevance_score` descending (most relevant first). `len(results)` is at most `min(top_k, len(documents))` when `top_k` is supplied; at most `len(documents)` otherwise. MAY be shorter than that bound if the provider returns fewer results (e.g., relevance-threshold filtering on the provider side). |
| `model` | The model identifier the provider returned. MAY be a more specific identifier than the one the provider was bound against. |
| `usage` | A `RerankUsage` record (defined below). |
| `response_id` | The provider-returned response identifier when present; null otherwise. Matches the OTel GenAI semconv `gen_ai.response.id` attribute (per observability §5.5.13) and the typed `RerankEvent.response_id` field (per graph-engine §6). |
| `raw` | The parsed provider response, as a language-idiomatic representation of deserialized JSON (Python: `dict[str, Any]`; TypeScript: `Record<string, unknown>`). MUST be populated on every successful return. Per charter §3.1 principle 8 ("Transparency over abstraction") — callers retain access to provider-specific fields the normalized shape doesn't surface. Parallel to llm-provider §6 `Response.raw` and §4 `EmbeddingResponse.raw`. |

### ScoredDocument

| Field | Description |
|---|---|
| `index` | Int. The 0-based position of this document in the original input `documents` list. **Load-bearing for caller-side lookup** — callers MUST be able to map a result back to its input document via `documents[result.index]`. Implementations MUST preserve this verbatim from the provider response. |
| `relevance_score` | Float. The provider-assigned relevance score; higher = more relevant. **Provider-specific scale** — most providers normalize to `[0.0, 1.0]` but the spec does NOT pin a scale. Cross-provider score comparisons are NOT meaningful. |
| `document` | The echoed document text when the provider returns it; null otherwise. Implementations MUST surface the provider's echo verbatim when present; MUST NOT fabricate the echo from the input `documents` list when the provider omits it (the provider's echo and the caller's input are two different surfaces; conflating them would mask provider-side document transformations like deduplication or truncation). |

### RerankUsage

| Field | Description |
|---|---|
| `search_units` | Int or null. The provider-reported count of "search units" billed for this call. Populated for providers that surface it (e.g., Cohere); null otherwise. |
| `input_tokens` | Int or null. The provider-reported count of input tokens (query + concatenated documents). Populated for providers that surface it (e.g., Voyage AI); null otherwise. |

Both fields default to null. Implementations MUST populate the field when the provider returns a
corresponding value and MUST NOT fabricate one when the provider omits it. A `RerankUsage` with both
fields null is valid and represents the "provider reports no billing surface" case.

### Cross-impl invariants

- `results` are sorted by `relevance_score` descending. Implementations that receive an unsorted
  provider response MUST sort before returning (some provider SDKs pre-sort; some don't).
- Each result's `index` MUST be a valid index into the input `documents` list
  (`0 <= index < len(documents)`). Implementations MUST raise `provider_invalid_response` (§7) when
  the provider returns an out-of-range index.
- The same `index` MUST NOT appear twice in `results`. Implementations MUST raise
  `provider_invalid_response` (§7) on duplicate-index responses.
- When `top_k` is supplied, `len(results) <= top_k`. Implementations MUST raise
  `provider_invalid_response` (§7) if the provider returns more results than requested.
- When the provider returns `document` echoes for some results but not others, implementations MUST
  preserve the per-result variance (null where the provider omitted; populated where the provider
  echoed). MUST NOT auto-fill from the input `documents` list.

## 7. Error semantics

The retrieval-provider capability inherits the llm-provider §7 error-category enumeration. The same
nine normative categories are available to both embedding and rerank calls. The retrieval-applicable
subset (the §7 categories minus the LLM-completion-specific ones), shared by both protocols, is:

- `provider_authentication` — credentials missing, invalid, or revoked.
- `provider_unavailable` — transport failure, provider-side outage, timeout.
- `provider_invalid_model` — bound model identifier not recognized by the provider.
- `provider_model_not_loaded` — model recognized but not currently usable.
- `provider_rate_limit` — provider-side rate limit signaled.
- `provider_invalid_response` — provider returned a malformed response: missing required fields, or a
  violation of the capability's cross-impl invariants (embedding §4 — mismatched vector count,
  inconsistent dimensions; rerank §6 — out-of-range or duplicate `index`, more results than `top_k`).
- `provider_invalid_request` — caller-supplied input failed pre-send validation (embedding: empty
  input list, invalid `dimensions`; rerank: empty `query`, empty `documents` list, `top_k <= 0`).

The following llm-provider §7 categories do NOT apply to embedding or rerank:

- `provider_unsupported_content_block` — both take strings, not content blocks.
- `structured_output_invalid` — neither has a `response_schema`.

The exception-flow contract from llm-provider §7 applies identically: the error category exception
MUST raise out of `embed()` / `rerank()` whether raised by the provider or by the implementation's
pre-send validation layer.

## 8. Wire-format mappings

Wire mappings are per-vendor / per-runtime realizations of the runtime-agnostic `EmbeddingProvider` /
`RerankProvider` contracts (§3 / §5) — the retrieval-provider analogue of llm-provider §8. Each mapping
pins the wire shapes, the construction parameters (e.g. `base_url`), and the per-mapping realization of
cross-vendor knobs (`input_type`). Mappings are normative: a conforming implementation of a given
mapping MUST produce the wire requests and consume the wire responses described here.

### 8.1 TEI (Text Embeddings Inference)

HuggingFace Text Embeddings Inference is a self-hosted serving runtime. Its `gen_ai.system` identifier
is `"tei"` (per observability §5.5.8 / §5.5.13 — identify the wire surface, not the model developer).
The `/embed` and `/rerank` wire shapes below were verified against the TEI OpenAPI; `docs/compatibility.md`
records the verified version.

**Construction (two separate instances).** TEI hosts one model per instance, and embedding models and
cross-encoder rerankers are different model families — so a TEI `EmbeddingProvider` and a TEI
`RerankProvider` are distinct provider instances against distinct TEI deployments, each binding its own
`base_url` (§3 / §5 per-instance binding):

- the **TEI `EmbeddingProvider`** binds `base_url` (the embedding instance) + the bound model + an
  `input_type` → `prompt_name` map (e.g. `{query: "query", document: "passage"}`) realizing asymmetric
  embedding via TEI's native server-side prompts, with OPTIONAL client-side `query_prefix` /
  `document_prefix` strings as the fallback for models without configured prompts;
- the **TEI `RerankProvider`** binds `base_url` (the reranker instance) + the bound model + `chunk_size`
  (the rerank client-batch chunk size, default `32` — see *Mandatory rerank batch chunking*).

The spec does NOT enumerate per-model prefixes (model-specific, a moving target) — they are
operator-supplied at construction.

**`/embed`.** `POST {base_url}/embed` with `{"inputs": [str]}` (TEI accepts a string or array; the
mapping always sends the array form per §3's "always a list"); `EmbeddingRuntimeConfig.dimensions` maps
to TEI's `dimensions` field when set. The response is the vector array, in input order.

`input_type` realization: the mapping sends TEI's native `prompt_name` field, looked up from the
construction `input_type → prompt_name` map, so TEI applies the model's configured query/document
prompt **server-side** (the idiomatic path — TEI models carry named prompts in their config). For a
model without configured prompts, the mapping MAY instead prepend the construction-supplied
`query_prefix` / `document_prefix` **client-side**. Either way, `input_type` absent ⇒ no prompt and no
prefix (the symmetric default).

**`/rerank`.** `POST {base_url}/rerank` with `{"query": str, "texts": [str], "truncate": false, "return_text": <bool>}`.
TEI's `texts: [str]` maps directly onto `documents: list[str]` (§5; no per-document object wrapping);
`return_documents` (§6 rerank runtime config) → TEI's `return_text` (default `false`), surfacing the
echoed text on `ScoredDocument.document`. The response `[{"index": int, "score": float, "text"?: str}]`
maps onto `results` (§6): `index` → `ScoredDocument.index`, `score` → `relevance_score`, `text` →
`document`. Scores are normalized by default (`raw_scores: false`); the scale is model-specific (§6
pins none). TEI does not guarantee response sort order, so the mapping MUST sort per §6's "sort if the
provider didn't" invariant — subsumed by the chunk-and-stitch global re-sort below.

**Mandatory rerank batch chunking.** TEI enforces `max-client-batch-size` (server-configured, default
32). When `len(documents)` exceeds the instance's `chunk_size`, the mapping MUST split the documents
into consecutive ≤`chunk_size` chunks, issue one `/rerank` request per chunk (same `query`), and stitch
the results: re-base each chunk's `index` to its absolute position in the original `documents` list,
concatenate all `(index, score)` pairs, then apply §6's contract — sort by `score` descending and honor
`top_k`. This is valid because a cross-encoder scores each `(query, document)` pair independently of the
others in its batch. `chunk_size` is a construction parameter, default `32` (TEI's documented default;
an operator who lowered `--max-client-batch-size` sets it to match; an implementation MAY auto-detect
from TEI's `/info`). A mapping that does not chunk MUST NOT silently send an over-cap request; chunking
is required, not optional.

**`truncate: false` (fail-loud).** TEI's `truncate` defaults to `false`, so an over-length
`(query, document)` pair (or `/embed` input) errors rather than being silently truncated (model context
caps vary). The mapping sends `truncate: false` explicitly (leaving TEI's `truncation_direction`
default, `Right`); the resulting TEI error (HTTP 413 / 422) maps to `provider_invalid_request` (§7).

**Errors.** TEI HTTP / transport failures map to the §7 categories per the shared enumeration:
connection / 5xx → `provider_unavailable`; unknown model → `provider_invalid_model`; over-length /
malformed request (413 / 422) → `provider_invalid_request`; malformed response →
`provider_invalid_response`.

## 9. Determinism

Embedding model determinism guarantees vary by provider. This specification MUST NOT assume
bit-identical vectors for equivalent inputs across calls — providers MAY return slightly different
vectors for the same input (model-version updates, server-side non-determinism, etc.).

Embedding-aware caches keyed on input strings MAY apply per the provider's documented determinism
guarantees but are NOT a spec contract. A future proposal MAY define a cache-attribute family
analogous to proposal 0047's LLM prefix-cache attributes; out of scope for v1.

**Rerank determinism.** Rerank guarantees are similar to embedding's: providers MAY return slightly
different scores for the same `(query, documents)` pair across calls. This specification MUST NOT
assume bit-identical responses for equivalent inputs. Even when scores are identical bit-for-bit, two
documents with identical scores MAY appear in either order across calls (provider implementation
detail) unless the provider documents a tie-breaking rule; the spec MUST NOT assume one.

## 10. Cross-spec touchpoints

- **graph-engine §6** — typed observer events `EmbeddingEvent` / `EmbeddingFailedEvent` (embedding)
  and `RerankEvent` / `RerankFailedEvent` (rerank). See graph-engine §6 for the full event surface
  and dispatch contract.
- **observability §5.5** — OTel mapping for embedding spans (§5.5.8) and rerank spans (§5.5.13): the
  core GenAI semconv subset (per the §5.5 GenAI de-facto-standard carve-out) plus OA-namespace
  `openarmature.embedding.*` / `openarmature.rerank.*` attributes; span names
  `openarmature.embedding.complete` / `openarmature.rerank.complete` discriminate the operation.
- **observability §8** — Langfuse mapping using Langfuse's dedicated `Embedding` (§8.4.5) and
  `Retriever` (§8.4.7) observation types.
- **observability §5.5.4** — observer-level privacy flag `disable_provider_payload` (renamed from
  `disable_llm_payload` by proposal 0059) gates payload from any provider call, including embedding
  payload (`input_strings`, `request_extras`, the Langfuse `output` vectors) and rerank payload
  (`query`, `documents`, the result document echoes).
- **llm-provider §7** — error-category enumeration (inherited).
- **pipeline-utilities §6 (middleware)** — `EmbeddingProvider` and `RerankProvider` calls are
  eligible for retry middleware identically to `complete()` calls.

## 11. Out of scope

Not covered by this specification; deferred to follow-on capabilities or proposals:

- **Multi-modal embedding and rerank** — image / audio documents. Text-only in v1.
- **Further per-vendor and per-runtime wire-format mappings.** Beyond §8.1 (TEI), follow-on proposals
  add concrete vendor / runtime mappings — embedding (OpenAI, Cohere, Voyage, Jina) and rerank
  (Cohere, Voyage, Jina hosted) — each pinning the per-vendor wire sourcing for fields the protocol
  leaves position-agnostic (e.g., where `response_id` is surfaced in that vendor's response shape).
- **Per-SDK implementation details** — httpx batching strategies, provider-layer retry timing,
  SDK-specific error mapping. Provider-internal choices.
- **Caller-supplied determinism / seeding.** Embedding and rerank models rarely expose seeds; not v1.
- **Cross-call observability correlation** (e.g., "this rerank call used vectors from that embedding
  call"). Each call is independent at the protocol layer; any cross-call correlation lives in
  node-body code.
- **Embedding / rerank result caching at the framework level.** Caching is an application concern.
- **Streaming embeddings and streaming rerank.** Some providers stream results for very long inputs
  / large result sets; not v1.
- **Score normalization across providers.** Each rerank provider's relevance scale is surfaced
  as-returned; the spec does NOT define a normalization layer.
- **Hybrid retrieval (embedding + rerank in one call).** No provider exposes this as a single
  protocol-level operation; the two stages are always separate calls.
- **`gen_ai.operation.name` adoption for rerank.** Deferred per the stable-only upstream adoption
  policy; a follow-on proposal adds it when upstream reaches Stable with a rerank-applicable
  well-known value.
