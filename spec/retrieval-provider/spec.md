# Retrieval Provider

Canonical behavioral specification for the OpenArmature retrieval-provider abstraction.

- **Capability:** retrieval-provider
- **Introduced:** spec version 0.54.0

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
what the underlying provider returned. The `EmbeddingResponse.raw` field carries the provider
response verbatim — an object or an array (§4) — alongside the normalized fields, and the error categories preserve the underlying
provider exception as cause.

## 2. Concepts

**RetrievalProvider.** The umbrella term covering both `EmbeddingProvider` and `RerankProvider`. Not
a concrete protocol itself; used as the capability-level descriptor when discussing cross-protocol
concerns (observability, error semantics, per-model binding).

**EmbeddingProvider.** An object that, given a sequence of input strings, returns a sequence of
vectors wrapped in an `EmbeddingResponse`. Bound to a specific embedding model identifier per
instance.

**EmbeddingResponse.** The result of an `embed()` call: the vectors, the model identifier, the
verbatim provider response (`raw`), and — when present — usage information and the provider-returned request
identifier.

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
identifier, the verbatim provider response (`raw`), and — when present — usage information and the
provider-returned response identifier.

**RerankUsage.** A usage record with optional `search_units` and optional `input_tokens`, reflecting
the messy provider landscape where rerank pricing surfaces vary widely.

**ScoredDocument.** A single result entry carrying the document's original index in the input list,
the provider-assigned relevance score, and (optionally) an echo of the document text.

**Rerank runtime config.** A `RuntimeConfig`-shaped record (parallel to llm-provider §6) carrying
rerank-specific caller-supplied request parameters. Initially minimal: one declared field,
`return_documents` (boolean, default `False`), controlling whether the provider echoes document text
on each `ScoredDocument` in the response. The field name + default match the major rerank vendors'
wire-shape parameter (Voyage AI exposes `return_documents` defaulting `False`; Jina AI's wire default is `True`, so the §8.2 Jina mapping sends the OA value explicitly; Cohere's `/v2/rerank` has no `return_documents` field, so the §8.4 mapping treats the OA knob as a silent no-op);
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
span as the `openarmature.embedding.input_type` attribute (observability §5.5.8). Absent ⇒
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
| `usage` | An `EmbeddingUsage` record (defined below), or `null` when the provider reports no usage (e.g. TEI `/embed`, which returns a bare vector array with no usage object). Implementations MUST populate `usage` when the provider returns a usage record and MUST NOT fabricate one (an empty record, a zero, or a client-side token estimate) when it does not. |
| `response_id` | The provider-returned response identifier when present; null otherwise. Matches the OTel GenAI semconv `gen_ai.response.id` attribute (per observability §5.5.8) and the typed `EmbeddingEvent.response_id` field (per graph-engine §6). |
| `dimensions` | Int. The output vector dimensionality. MUST equal the length of each inner list in `vectors`. Derivable from `vectors[0]` but kept on the response for ergonomics and cross-vendor consistency. |
| `raw` | The verbatim deserialized JSON of the successful provider response — an object or an array (Python: `dict[str, Any] | list[Any]`; TypeScript: `Record<string, unknown> | unknown[]`), matching the response's top-level shape; the mapping MUST NOT wrap, rename, or reshape it to fit a container type. For a call that issues a single provider request this is that response; for a chunk-and-stitch call `raw` is the list of the per-request responses (§8 *Batch chunking*). MUST be populated on every successful return. Parallel to llm-provider §6 `Response.raw` **in intent** (verbatim provider response); the type differs because retrieval has array-response wire — e.g. TEI §8.1, whose `/embed` returns a bare vector array — that LLM completion does not, so `Response.raw` stays object-shaped. |

### EmbeddingUsage

| Field | Description |
|---|---|
| `input_tokens` | Int. Tokens billed for the embedding call. Present exactly when the `usage` record is (no `output_tokens` — vectors aren't tokens). |

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
| `usage` | A `RerankUsage` record (defined below), or `null` when the provider reports no usage (e.g. TEI `/rerank`). A record is present when the provider surfaces at least one usage figure; its `input_tokens` / `search_units` stay individually nullable (below). Same populate/don't-fabricate rule as §4. |
| `response_id` | The provider-returned response identifier when present; null otherwise. Matches the OTel GenAI semconv `gen_ai.response.id` attribute (per observability §5.5.13) and the typed `RerankEvent.response_id` field (per graph-engine §6). |
| `raw` | The verbatim deserialized JSON of the successful provider response — an object or an array (Python: `dict[str, Any] | list[Any]`; TypeScript: `Record<string, unknown> | unknown[]`), matching the response's top-level shape; the mapping MUST NOT wrap, rename, or reshape it to fit a container type. For a call that issues a single provider request this is that response; for a chunk-and-stitch call `raw` is the list of the per-request responses (§8 *Batch chunking*; §8.1 for TEI rerank). MUST be populated on every successful return. Per charter §3.1 principle 8 ("Transparency over abstraction") — callers retain access to provider-specific fields the normalized shape doesn't surface (e.g. TEI `/rerank`'s chunk-relative indices, which `results` re-bases to absolute positions and re-sorts). Parallel to llm-provider §6 `Response.raw` and §4 `EmbeddingResponse.raw` **in intent**; the type differs because retrieval has array-response wire. |

### ScoredDocument

| Field | Description |
|---|---|
| `index` | Int. The 0-based position of this document in the original input `documents` list. **Load-bearing for caller-side lookup** — callers MUST be able to map a result back to its input document via `documents[result.index]`. Implementations MUST preserve this verbatim from the provider response. |
| `relevance_score` | Float. The provider-assigned relevance score; higher = more relevant. **Provider-specific scale** — most providers normalize to `[0.0, 1.0]` but the spec does NOT pin a scale. Cross-provider score comparisons are NOT meaningful. |
| `document` | The echoed document **text** when the provider returns it; `null` otherwise. When the provider echoes the document as a **string**, implementations MUST surface it verbatim (an empty string is *present* — surfaced as `""`, not folded to `null`). When the provider echoes it as an **object** (a wrapper carrying the text under a `text` key), implementations MUST surface the object's text content — an object with a **string-valued `text` key** → that string; any other object (no string `text`, or a non-text media shape) → `null` — with the verbatim echo object preserved on `RerankResponse.raw` (the transparency surface, where a caller recovers a non-text echo, e.g. an image). An echo that is neither a string, an object, nor absent/`null` — a number, boolean, or array — is not a valid document shape and is a malformed provider response (`provider_invalid_response`, §7). Implementations MUST NOT fabricate the echo from the input `documents` list when the provider omits it (the provider's echo and the caller's input are two different surfaces; conflating them would mask provider-side document transformations like deduplication or truncation). |

### RerankUsage

| Field | Description |
|---|---|
| `search_units` | Int or null. The provider-reported count of "search units" billed for this call. Populated for providers that surface it (e.g., Cohere); null otherwise. |
| `input_tokens` | Int or null. The provider-reported count of input tokens (query + concatenated documents). Populated for providers that surface it (e.g., Voyage AI); null otherwise. |

Both fields default to null. Implementations MUST populate the field when the provider returns a
corresponding value and MUST NOT fabricate one when the provider omits it. A provider that surfaces
*some* usage (e.g. Cohere's `search_units` without `input_tokens`) yields a record with the reported
field(s) set and the rest null. A provider that surfaces *no* usage yields `usage = null` (§6 field
table), not an all-null record — a `RerankUsage` record is present only when at least one figure is
reported.

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
- When the provider returns `document` echoes for some results but not others — or as different shapes
  per result — implementations MUST preserve the per-result variance: `null` where the provider omitted
  the echo **or echoed a non-text object** (an object without a string `text`, per the `document` row
  above), populated with the echoed text where the provider echoed a string or a text-bearing object.
  MUST NOT auto-fill from the input
  `documents` list.

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

**Batch chunking.** When an embedding mapping's provider enforces a maximum input count per request and a
caller's input list exceeds it, the mapping MUST: (1) split the inputs into consecutive chunks of at most
the provider's per-call cap, preserving order; (2) issue one request per chunk with **every request field
other than the chunked input list identical** across chunks (model, the `input_type` realization,
dimensions / `output_dimension`, `embedding_types`, truncation, and any extras-bag fields); (3) stitch the
responses — concatenate the per-chunk vectors in the original input order, so §4's one-vector-per-input
and input-order invariants hold across the whole call; and (4) combine the per-chunk usage per §4's
(now nullable) usage contract — sum the `EmbeddingUsage.input_tokens` when the provider reports usage,
or produce `usage = null` when it reports none (e.g. TEI `/embed`). `EmbeddingResponse.response_id` is the first chunk's response id (a
single-request call uses that request's id). `EmbeddingResponse.raw` is the **list of the
per-chunk responses**, in request order — each entry the verbatim deserialized JSON of that request's
response per §4 (a single-request call's `raw` is that one response, not a one-element list). A mapping MUST NOT silently send an over-cap request. When a
provider enforces **no** per-call cap (it batches server-side), no client-side chunking is required. This
generalizes to the embedding side, across all mappings, the per-item-independence chunk-and-stitch §8.1
applies to TEI rerank; each mapping's cap is the provider's documented per-call limit, noted in that
mapping's section and recorded in `docs/compatibility.md`.

### 8.1 TEI (Text Embeddings Inference)

HuggingFace Text Embeddings Inference is a self-hosted serving runtime. Its `gen_ai.system` identifier
is `"tei"` (per observability §5.5.8 / §5.5.13 — identify the wire surface, not the model developer).
The `/embed` and `/rerank` wire shapes below were verified against the TEI OpenAPI; `docs/compatibility.md`
records the verified version.

**Construction (two separate instances).** TEI hosts one model per instance, and embedding models and
cross-encoder rerankers are different model families — so a TEI `EmbeddingProvider` and a TEI
`RerankProvider` are distinct provider instances against distinct TEI deployments, each binding its own
`base_url` (§3 / §5 per-instance binding):

- the **TEI `EmbeddingProvider`** binds `base_url` (the embedding instance) + the bound model +
  `chunk_size` (the embed client-batch chunk size, default `32` — TEI's `max-client-batch-size`, per the
  §8 *Batch chunking* rule) + an `input_type` → `prompt_name` map (e.g. `{query: "query", document: "passage"}`)
  realizing asymmetric embedding via TEI's native server-side prompts, with OPTIONAL client-side
  `query_prefix` / `document_prefix` strings as the fallback for models without configured prompts;
- the **TEI `RerankProvider`** binds `base_url` (the reranker instance) + the bound model + `chunk_size`
  (the rerank client-batch chunk size, default `32` — see *Mandatory rerank batch chunking*).

The spec does NOT enumerate per-model prefixes (model-specific, a moving target) — they are
operator-supplied at construction.

**`/embed`.** `POST {base_url}/embed` with `{"inputs": [str]}` (TEI accepts a string or array; the
mapping always sends the array form per §3's "always a list"); `EmbeddingRuntimeConfig.dimensions` maps
to TEI's `dimensions` field when set. The response is the vector array, in input order. Like `/rerank`,
`/embed` is bounded by TEI's `max-client-batch-size` (the construction `chunk_size`, default 32); an
over-cap embed call chunk-and-stitches per the §8 *Batch chunking* rule. TEI `/embed` returns no usage
object, so `EmbeddingResponse.usage` is `null` — the mapping MUST NOT fabricate a usage record or a
zero (§4).

`input_type` realization: the mapping sends TEI's native `prompt_name` field, looked up from the
construction `input_type → prompt_name` map, so TEI applies the model's configured query/document
prompt **server-side** (the idiomatic path — TEI models carry named prompts in their config). For a
model without configured prompts, the mapping MAY instead prepend the construction-supplied
`query_prefix` / `document_prefix` **client-side**. Either way, `input_type` absent ⇒ no prompt and no
prefix (the symmetric default).

**`/rerank`.** `POST {base_url}/rerank` with `{"query": str, "texts": [str], "truncate": false, "return_text": <bool>}`.
TEI's `texts: [str]` maps directly onto `documents: list[str]` (§5; no per-document object wrapping);
`return_documents` (§2 rerank runtime config) → TEI's `return_text` (default `false`), surfacing the
echoed text on `ScoredDocument.document`. The response `[{"index": int, "score": float, "text"?: str}]`
maps onto `results` (§6): `index` → `ScoredDocument.index`, `score` → `relevance_score`, `text` →
`document`. Scores are normalized by default (`raw_scores: false`); the scale is model-specific (§6
pins none). TEI does not guarantee response sort order, so the mapping MUST sort per §6's "sort if the
provider didn't" invariant — subsumed by the chunk-and-stitch global re-sort below. TEI `/rerank`
returns no usage object, so `RerankResponse.usage` is `null` — the mapping MUST NOT fabricate a
`RerankUsage` record (§6).

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

**`raw` shape.** TEI returns bare JSON arrays on both endpoints, so a single-request `raw` is that array —
`/embed`'s `[[float, …], …]` or `/rerank`'s `[{index, score, text?}]` (§4 / §6) — never an OA-wrapped
object. A chunk-and-stitch call's `raw` is the **list of the per-chunk arrays**, in request order (one level
deeper than a single-request `raw`; §8's batch-chunking rule for embed, the mandatory rerank chunking above for rerank).
Because both a single response and a chunked `raw` are a `list`, the container type alone does not
distinguish them; the discriminator is whether the input exceeded `chunk_size` (the chunk trigger). For
`/embed` the chunked `raw` is largely redundant with the fully-stitched `vectors`; for `/rerank` it is
**not** — each chunk's array carries **chunk-relative** `index` values in the provider's order, which the
stitched `results` re-bases to absolute positions and re-sorts by score, so `raw` preserves index / order
information `results` reshapes away.

**`truncate: false` (fail-loud).** TEI's `truncate` defaults to `false` on both endpoints, so an
over-length input errors rather than being silently truncated (model context caps vary). The `/rerank`
mapping sends `truncate: false` **explicitly** (leaving TEI's `truncation_direction` default, `Right`) —
the surface where a silently truncated `(query, document)` pair would yield a wrong relevance score; the
resulting TEI error (HTTP 413 / 422) maps to `provider_invalid_request` (§7). The `/embed` mapping
relies on TEI's `false` default and does **not** add `truncate` to the request, keeping the body minimal
(`{inputs[, prompt_name][, dimensions]}`) and byte-identical to the symmetric path when `input_type` is
absent.

**Errors.** TEI HTTP / transport failures map to the §7 categories per the shared enumeration:
connection / 5xx → `provider_unavailable`; unknown model → `provider_invalid_model`; over-length /
malformed request (413 / 422) → `provider_invalid_request`; malformed response →
`provider_invalid_response`.

### 8.2 Jina

Jina AI is a hosted retrieval API. Its `gen_ai.system` identifier is `"jina"` (per observability §5.5.8 / §5.5.13 —
identify the wire surface, not the model developer). The wire shapes below were verified against the
Jina OpenAPI; `docs/compatibility.md` records the verified version.

**Construction.** A Jina provider instance binds an **API key** (sent as `Authorization: Bearer <key>`)
+ the bound model identifier (§3 / §5 per-instance binding), with `base_url` defaulting to
`https://api.jina.ai` (origin only — the `/v1` version stays in the route; override for a proxy /
private gateway). A Jina `EmbeddingProvider` (`/v1/embeddings`) and a Jina `RerankProvider`
(`/v1/rerank`) are distinct instances (one model each) sharing the hosted endpoint.

**`/v1/rerank`.** `POST {base_url}/v1/rerank` with
`{"model": str, "query": str, "documents": [str], "top_n"?: int, "return_documents": <bool>, "truncation": false}`.
`documents` ← `documents` (§5); `top_n` ← `top_k` (§5); `return_documents` ← the
`RerankRuntimeConfig.return_documents` value, **sent explicitly** — Jina's wire default is `true`, but
OA's default is `False` (§2), so the mapping sends the OA value rather than relying on Jina's default.
The response `{model, usage: {total_tokens}, results: [{index, relevance_score, document?}]}` maps onto
`results` (§6): `index` → `ScoredDocument.index`, `relevance_score` → `relevance_score`, the `document`
echo per the shape rule below; `usage.total_tokens` → `RerankUsage.input_tokens` (Jina meters rerank by
tokens, not search units). Results are returned ranked; the mapping applies §6's "sort if the provider
didn't" invariant regardless.

**`document` echo shape.** Jina's rerank result `document` is `anyOf[string, TextDoc, ImageDoc, null]`
(`TextDoc = {"text": str}`, `ImageDoc = {"image": str}`); the text reranker typically returns the `TextDoc`
object. Realizing §6's object-echo rule: a `string` → itself; a `TextDoc` → its `text`; an `ImageDoc` (or
any object without a string `text`) → `null`; absent / `null` → `null`. The verbatim echo object is
preserved on `RerankResponse.raw`. A `TextDoc` / `ImageDoc` is a documented Jina shape, so the mapping MUST
NOT treat it as malformed, and an object echo that is neither (no string `text`) still surfaces `null` per
the §6 rule — its verbatim shape stays on `RerankResponse.raw` — rather than raising. A `document` echo
that is **not** a string, object, or `null` — a number, array, or boolean — is not a valid document shape
and maps to `provider_invalid_response` (§7); the `null` fallback covers text-less object echoes, not
non-object wire corruption.

**`/v1/embeddings`.** `POST {base_url}/v1/embeddings` with
`{"model": str, "input": [str], "task"?: str, "dimensions"?: int, "truncate": false}`. **`input_type`
realization:** the mapping sets Jina's native `task` from `input_type` — `"query"` → `"retrieval.query"`,
`"document"` → `"retrieval.passage"` — so Jina applies the model-appropriate query/passage representation
server-side; `input_type` absent ⇒ `task` omitted. The mapping recognizes a **closed `input_type` set**
(`query` / `document`); an unrecognized value is a pre-send `provider_invalid_request` (§7). Jina's other
`task` values (e.g. `text-matching`, `classification`, `clustering` — model-dependent) are reached via
the extras-pass-through bag, not `input_type` (widening `input_type`'s normative value space is a
protocol-level change, deferred until a consumer needs it). `EmbeddingRuntimeConfig.dimensions` → Jina's
`dimensions` (Matryoshka) when set. The response `{model, usage, data: [{index, embedding}]}` maps to the
`EmbeddingResponse` vectors in input order. Jina enforces **no** per-call input cap (it batches
server-side by token count), so the §8 *Batch chunking* rule's no-cap branch applies — the embed mapping
does not chunk client-side.

**`truncation` / `truncate` (fail-loud).** Jina names the flag `truncation` on `/v1/rerank` and
`truncate` on `/v1/embeddings` (vendor inconsistency); the mapping sends the per-endpoint flag `false`
so an over-length input errors rather than being silently truncated (consistent with §8.1's TEI
fail-loud posture).

**Errors.** Jina HTTP failures map to the §7 categories per the shared enumeration: `401` →
`provider_authentication`; `429` (rate limit) → `provider_rate_limit`; `5xx` → `provider_unavailable`;
unknown model (`404`) → `provider_invalid_model`; over-length / malformed request (`422`) →
`provider_invalid_request`; malformed response → `provider_invalid_response`.

### 8.3 OpenAI-compatible embeddings

The OpenAI `/v1/embeddings` wire is the de-facto-standard embedding API, exposed by OpenAI and the
OpenAI-compatible serving ecosystem (vLLM, LocalAI, Together, TEI's own OpenAI-compatible endpoint, …).
`gen_ai.system` is `"openai"` — identifying the **wire surface**, not the backing deployment (per
§5.5.8 / §5.5.13; a vLLM / LocalAI backend reached through this wire is still the OpenAI wire surface).
Wire shapes verified against the OpenAI OpenAPI; `docs/compatibility.md` records the verified version.
**Embeddings-only** — OpenAI exposes no rerank API, so this mapping has no `RerankProvider` counterpart.

**Construction.** An OpenAI-compatible `EmbeddingProvider` binds an **API key** (sent as
`Authorization: Bearer <key>`) + the bound model identifier (§3 / §5 per-instance binding), with
`base_url` defaulting to `https://api.openai.com` (origin only — the `/v1` version stays in the route,
consistent with §8.1 / §8.2) and overridable for any OpenAI-compatible backend. It MAY additionally
bind the optional client-side `query_prefix` / `document_prefix` from §8.1 — off by default
(pure-symmetric OpenAI), set only for an asymmetric model served behind a compatible endpoint (see
*`input_type`* below).

**`/v1/embeddings`.** `POST {base_url}/v1/embeddings` with
`{"model": str, "input": [str], "dimensions"?: int}`. `input` is always the array form (§3's "always a
list"); `EmbeddingRuntimeConfig.dimensions` → wire `dimensions` (Matryoshka, on models that support it)
when set. The mapping does **not** send `encoding_format` by default (OpenAI's wire default is
`"float"`); `"base64"` rides the extras-pass-through bag. The response
`{object: "list", data: [{object: "embedding", index, embedding}], model, usage: {prompt_tokens, total_tokens}}`
maps to the `EmbeddingResponse` vectors in input order — the mapping consumes `data` + `usage` (the
`object` fields are OpenAI wire metadata); `usage.prompt_tokens` → `EmbeddingUsage.input_tokens`
(embedding has no output tokens, so `total_tokens` equals `prompt_tokens`). OpenAI `/v1/embeddings`
enforces a per-call cap of 2048 inputs (plus a summed-token ceiling); an over-cap call chunk-and-stitches
per the §8 *Batch chunking* rule.

**`input_type` (symmetric base wire; client-side prefix for asymmetric).** The OpenAI `/v1/embeddings`
wire has no query/document parameter, so on the base wire `input_type` is **not realized** — an absent
`input_type` is the correct symmetric default for OpenAI's symmetric models (e.g. `text-embedding-3`),
and the mapping does not error on it. For an **asymmetric** model served behind a compatible endpoint
(e.g. a BGE / E5 model on vLLM), the mapping applies the **client-side prefix** from §8.1: when
`query_prefix` / `document_prefix` are bound at construction, `input_type` selects which to prepend
before sending — the only way to express the distinction on a wire with no `input_type` field. A server
that *extends* the wire with its own `input_type`-style field instead takes it through the
extras-pass-through bag.

**Errors.** HTTP failures map to the §7 categories per the shared enumeration: `401` →
`provider_authentication`; `429` (rate limit) → `provider_rate_limit`; `5xx` → `provider_unavailable`;
unknown model (`404`) → `provider_invalid_model`; malformed / oversized request (`400`) →
`provider_invalid_request`; malformed response → `provider_invalid_response`.

### 8.4 Cohere

Cohere is a hosted retrieval API; this mapping covers both Cohere endpoints — rerank (`/v2/rerank`) and
embeddings (`/v2/embed`). Its `gen_ai.system` identifier is `"cohere"` (per observability §5.5.8 /
§5.5.13 — identify the wire surface, not the model developer). The wire shapes below were verified
against the Cohere v2 API reference; `docs/compatibility.md` records the verified version.

**Construction.** A Cohere provider instance binds an **API key** (sent as `Authorization: Bearer <key>`)
+ the bound model identifier (§3 / §5 per-instance binding), with `base_url` defaulting to
`https://api.cohere.com` (origin only — the `/v2` version stays in the route, consistent with §8.2 /
§8.3; override for a proxy / private gateway). A Cohere `EmbeddingProvider` (`/v2/embed`) and a Cohere
`RerankProvider` (`/v2/rerank`) are distinct instances (one model each) sharing the hosted endpoint —
the §8.2 Jina pattern.

**`/v2/rerank`.** `POST {base_url}/v2/rerank` with `{"model": str, "query": str, "documents": [str], "top_n"?: int}`.
`documents` ← `documents` (§5), sent as the **string-array** form (Cohere v2 takes strings only — the v1
list-of-objects / `rank_fields` form is not used); `top_n` ← `top_k` (§5), omitted when the caller passed
`None`. The response
`{"id": str, "results": [{"index": int, "relevance_score": float}], "meta": {"billed_units": {"search_units": int}}}`
maps onto §6: each `results` entry's `index` → `ScoredDocument.index`, `relevance_score` →
`ScoredDocument.relevance_score`; `meta.billed_units.search_units` → `RerankUsage.search_units`
(`RerankUsage.input_tokens` stays null — Cohere does not report a token count); top-level `id` →
`RerankResponse.response_id`. Cohere's rerank response echoes no `model` field, so `RerankResponse.model`
is the bound model identifier. Cohere returns results ranked, but the mapping applies §6's "sort if the
provider didn't" invariant regardless, and enforces §6's valid-`index` / no-duplicate-`index` /
result-count (`len(results) <= top_k` when `top_k` is supplied, else `<= len(documents)`) invariants
against the response.

**`return_documents` (not realized — a silent no-op).** The `/v2/rerank` wire has **no `return_documents`
parameter and never echoes document text** (results carry `index` + `relevance_score` only). So
`RerankRuntimeConfig.return_documents` (§2) is **not realized** on this wire: the mapping does not add any
wire field for it, leaves `ScoredDocument.document` **null on every result regardless of the config
value**, and does **not** error when `return_documents=True` is requested — the same "knob with no wire to
land on is a silent no-op" path §8.3 takes for `input_type` on the symmetric OpenAI wire. This is
consistent with §6's rule that an implementation MUST NOT fabricate the echo from the input `documents`
list when the provider omits it; callers recover the document text via `documents[result.index]` (the
`index` field is the load-bearing lookup key).

**`max_tokens_per_doc` / truncation (no fail-loud).** Unlike §8.1 (TEI) and §8.2 (Jina), which send a
`truncate: false` / `truncation: false` flag so an over-length input **errors** rather than being
silently truncated, the Cohere `/v2/rerank` wire has **no fail-loud option** — Cohere truncates each
over-length document server-side to `max_tokens_per_doc` (Cohere's wire default `4096`). The mapping
therefore does not realize §8.1 / §8.2's fail-loud posture (the wire cannot express it); OA has no
declared truncation field, so `max_tokens_per_doc` rides the **extras-pass-through bag** (absent ⇒
Cohere's `4096` default applies). This vendor divergence is stated explicitly per charter §3.1 principle 8
(transparency over abstraction).

**`/v2/embed`.** `POST {base_url}/v2/embed` with
`{"model": str, "input_type": str, "texts": [str], "embedding_types": ["float"], "truncate": "NONE", "output_dimension"?: int}`.
`texts` ← the input strings (always the array form per §3's "always a list"; the multimodal `inputs` /
`images` form is out of scope — §11). The response
`{"id": str, "embeddings": {"float": [[float, …], …]}, "texts": [str], "meta": {"billed_units": {"input_tokens": int}}}`
maps onto §4: `embeddings.float` → the `EmbeddingResponse` vectors **in input order**;
`meta.billed_units.input_tokens` → `EmbeddingUsage.input_tokens`; top-level `id` →
`EmbeddingResponse.response_id`. Cohere's embed response echoes no `model` field, so
`EmbeddingResponse.model` is the bound model identifier. The §4 cross-impl invariants (one vector per
input, input-order keying, uniform dimensionality) are enforced against `embeddings.float`.

**`input_type` (mandatory wire field).** Cohere v2 `/v2/embed` **requires** `input_type`, so — unlike
§8.1 / §8.2 (where an absent `input_type` omits the wire field) and §8.3 (symmetric no-op) — this mapping
MUST always send a value. It recognizes the **closed `input_type` set** (`query` / `document`, per §8.2's
treatment): `query` → `search_query`, `document` → `search_document`. An absent `input_type` MUST map to
`search_document` — the conventional bulk-indexing default (the wire requires a value; storing document
vectors is the dominant case). An unrecognized OA `input_type` value is a pre-send
`provider_invalid_request` (§7). Cohere's other `input_type` values (`classification` / `clustering` /
`image`) are reached via the extras-pass-through bag, not OA's `input_type` (widening `input_type`'s
normative value space is a §2 / 0077 protocol-level change, deferred until a consumer needs it).

**`output_dimension` / `embedding_types` / `truncate` (fail-loud).** `EmbeddingRuntimeConfig.dimensions` →
Cohere's **`output_dimension`** (Cohere's name for the Matryoshka knob; supported on `embed-v4` and newer
models) when set; omitted otherwise (Cohere's model default applies). The mapping requests
`embedding_types: ["float"]` **explicitly** (so the type-keyed response is guaranteed to carry the
`embeddings.float` key the mapping reads) and consumes `embeddings.float`; other precisions (`int8` /
`uint8` / `binary` / `ubinary` / `base64`) ride the extras-pass-through bag. It sends `truncate: "NONE"`
so an over-length input **errors** (surfacing `provider_invalid_request` per §7) rather than being
silently truncated — the §8.2 Jina embed fail-loud posture, and the point where §8.4's embed half
diverges from its rerank half (which has no fail-loud option).

**Batch chunking.** Cohere `/v2/embed` enforces a **96-input per-call cap**; an over-cap call
chunk-and-stitches per the §8 *Batch chunking* rule (consecutive ≤96 chunks, identical per-call
parameters, the per-chunk `embeddings.float` concatenated in input order, `meta.billed_units.input_tokens`
summed, `response_id` the first chunk's `id`).

**Errors.** Cohere HTTP failures map to the §7 categories per the shared enumeration: `401` →
`provider_authentication`; `429` (rate limit) → `provider_rate_limit`; `5xx` → `provider_unavailable`;
unknown model (`404`) → `provider_invalid_model`; malformed / invalid request (`400`) →
`provider_invalid_request`; malformed response → `provider_invalid_response`.

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
- **Further per-vendor and per-runtime wire-format mappings.** Beyond §8.1 (TEI), §8.2 (Jina), §8.3
  (OpenAI-compatible embeddings), and §8.4 (Cohere rerank + embeddings), follow-on proposals add the
  remaining vendor mappings — Voyage AI (embedding + rerank) — each pinning the per-vendor wire
  sourcing for fields the protocol leaves position-agnostic (e.g., where `response_id` is surfaced in
  that vendor's response shape).
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

## History

- created by [proposal 0059](../../proposals/0059-retrieval-provider-embedding.md)
- rerank protocol added by [proposal 0060](../../proposals/0060-retrieval-provider-rerank.md)
- Cohere rerank wire mapping (§8.4) added by [proposal 0090](../../proposals/0090-retrieval-provider-cohere-rerank-wire.md)
- Cohere `/v2/embed` endpoint (extends §8.4) added by [proposal 0091](../../proposals/0091-retrieval-provider-cohere-embeddings-wire.md)
- §8 general embedding-mapping batch-chunking rule added by [proposal 0092](../../proposals/0092-retrieval-provider-embedding-batch-chunking.md)
- `EmbeddingResponse.usage` (§4) and `RerankResponse.usage` (§6) made nullable (`record | null` — `null` when the provider reports no usage), reconciling the response types with the record-null model the typed events (graph-engine §6) and §11 metric already use; §2 concept lines qualify usage "(when present)", §8.1 pins TEI `/embed` + `/rerank` `usage = null`, and §8's batch-chunking step 4 combines usage record-aware by [proposal 0093](../../proposals/0093-nullable-provider-usage-records.md)
- `EmbeddingResponse.raw` (§4) and `RerankResponse.raw` (§6) widened from `dict[str, Any]` to `dict | list` — the verbatim deserialized JSON of the successful response whatever its top-level shape (an array for bare-array wire like TEI §8.1); the mapping MUST NOT wrap or reshape it. §8's batch-chunking rule gains a `raw` stitch clause and §8.1 a `raw` note: a chunk-and-stitch call's `raw` is the list of the per-request responses (nothing lost across chunks), the normalized fields staying ergonomic summaries. Scoped to retrieval-provider — llm-provider `Response.raw` unchanged by [proposal 0096](../../proposals/0096-retrieval-raw-json-shape.md)
- `ScoredDocument.document` (§6) generalized to **object-shaped echoes**: an object echo surfaces its text content (a string-valued `text` key → that string, else `null`), an empty string is present (→ `""`), and the verbatim echo object is preserved on `RerankResponse.raw`; the "surface verbatim" MUST and the per-result null-dichotomy invariant amended (`null` now = omitted OR a non-text-shape echo). §8.2 Jina realizes it for `document: anyOf[string, TextDoc, ImageDoc, null]` (`TextDoc` → `text`, `ImageDoc` / text-less object → `null`, a non-object echo — number / array / boolean → `provider_invalid_response`), replacing the prior `document → document` direct mapping; fixture 019 gains TextDoc / ImageDoc→`null` / mixed-shape cases by [proposal 0097](../../proposals/0097-retrieval-provider-jina-document-echo-shape.md)
