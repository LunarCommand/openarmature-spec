# Retrieval Provider

Canonical behavioral specification for the OpenArmature retrieval-provider abstraction.

- **Capability:** retrieval-provider
- **Introduced:** spec version 0.54.0
- **History:**
  - created by [proposal 0059](../../proposals/0059-retrieval-provider-embedding.md)

This specification is language-agnostic. Each implementation (Python, TypeScript, …) maps its own idioms
onto the behavioral contract described here. Conformance is verified by the fixtures under `conformance/`.

Normative keywords (MUST, MUST NOT, SHOULD, MAY) are used per [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## 1. Purpose

The retrieval-provider capability is the home for retrieval-primitive provider operations that sit
alongside LLM completion. The first protocol surface this specification defines is **embedding** —
turning a list of input strings into a list of vectors via an `EmbeddingProvider`. A sibling
`RerankProvider` protocol covering re-ranking lands in a forthcoming proposal extending the same
capability.

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

**RetrievalProvider.** The umbrella term covering both `EmbeddingProvider` (this specification) and
the forthcoming `RerankProvider`. Not a concrete protocol itself; used as the capability-level
descriptor when discussing cross-protocol concerns (observability, error semantics, per-model
binding).

**EmbeddingProvider.** An object that, given a sequence of input strings, returns a sequence of
vectors wrapped in an `EmbeddingResponse`. Bound to a specific embedding model identifier per
instance.

**EmbeddingResponse.** The result of an `embed()` call: the vectors, the model identifier, usage
information, and (when present) the provider-returned request identifier and the parsed raw
response.

**EmbeddingUsage.** A usage record carrying `input_tokens` only — embedding has no output tokens
(vectors aren't tokens).

**Embedding runtime config.** A `RuntimeConfig`-shaped record (parallel to llm-provider §6) carrying
embedding-specific caller-supplied request parameters. Initially minimal: an optional `dimensions`
field (for callers controlling output vector size on providers that support it) plus the
extras-pass-through bag for vendor-specific knobs.

## 3. EmbeddingProvider protocol

The `EmbeddingProvider` protocol exposes two async operations.

### `ready()`

A no-argument async operation that verifies the provider can serve requests against the bound
model. Implementations MAY surface a hosted-provider authentication check, a local-model load
attempt, or a noop — whichever fits the backend. The operation:

- MUST be idempotent. Repeated `ready()` calls MUST NOT change observable provider state.
- MUST surface `provider_invalid_model` (per §5) if the bound embedding model is not recognized by
  the backend.
- MUST surface `provider_model_not_loaded` (per §5) if the bound model is recognized but not
  currently usable (e.g., a local model that requires explicit loading).
- MAY raise other §5 error categories (`provider_authentication`, `provider_unavailable`) when the
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
- MUST raise one of the §5 error categories on failure. The §5 enumeration is shared cross-
  capability with llm-provider §7; embedding-applicable subset documented in §5.
- MUST preserve input order in the response (the vector at index `i` MUST be the embedding of
  `input[i]`). Implementations MUST NOT permute vector position relative to input position.
- MUST NOT loop, retry, or fall back. Pipeline-utilities §6 middleware and per-call retry compose
  above the provider for those concerns.

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
  on the response and raise `provider_invalid_response` (§5) if violated.
- The `dimensions` field on the response MUST equal the dimensionality of each inner vector —
  cross-check invariant for adapters.
- Implementations MUST raise `provider_invalid_response` (§5) when the response carries a mismatched
  count of vectors vs. input strings.

## 5. Error semantics

The retrieval-provider capability inherits the llm-provider §7 error-category enumeration. The same nine normative categories are available to embedding calls.
The embedding-applicable subset (the §7 categories minus the LLM-completion-specific ones) is:

- `provider_authentication` — credentials missing, invalid, or revoked.
- `provider_unavailable` — transport failure, provider-side outage, timeout.
- `provider_invalid_model` — bound model identifier not recognized by the provider.
- `provider_model_not_loaded` — model recognized but not currently usable.
- `provider_rate_limit` — provider-side rate limit signaled.
- `provider_invalid_response` — provider returned a malformed response (mismatched vector count,
  inconsistent dimensions, missing required fields).
- `provider_invalid_request` — caller-supplied input failed pre-send validation (empty input list,
  invalid `dimensions` value, etc.).

The following llm-provider §7 categories do NOT apply to embedding:

- `provider_unsupported_content_block` — embedding takes strings, not content blocks.
- `structured_output_invalid` — embedding has no `response_schema`.

The exception-flow contract from llm-provider §7 applies identically: the error category exception
MUST raise out of `embed()` whether raised by the provider or by the implementation's pre-send
validation layer.

## 6. Determinism

Embedding model determinism guarantees vary by provider. This specification MUST NOT assume
bit-identical vectors for equivalent inputs across calls — providers MAY return slightly different
vectors for the same input (model-version updates, server-side non-determinism, etc.).

Embedding-aware caches keyed on input strings MAY apply per the provider's documented determinism
guarantees but are NOT a spec contract. A future proposal MAY define a cache-attribute family
analogous to proposal 0047's LLM prefix-cache attributes; out of scope for v1.

## 7. Cross-spec touchpoints

- **graph-engine §6** — typed observer events `EmbeddingEvent` (success) and `EmbeddingFailedEvent`
  (failure). See graph-engine §6 for the full event surface and dispatch contract.
- **observability §5.5** — OTel mapping for embedding spans (Stable GenAI semconv subset plus
  OA-namespace `openarmature.embedding.*` attributes; span name
  `openarmature.embedding.complete` discriminates the operation).
- **observability §8** — Langfuse mapping using Langfuse's dedicated `Embedding` observation type.
- **observability §5.5.4** — observer-level privacy flag `disable_provider_payload` (renamed from
  `disable_llm_payload` by proposal 0059) gates payload from any provider call, including
  embedding payload (`input_strings`, `request_extras`, and the Langfuse `output` vectors).
- **llm-provider §7** — error-category enumeration (inherited).
- **pipeline-utilities §6 (middleware)** — `EmbeddingProvider` calls are eligible for retry
  middleware identically to `complete()` calls.

## 8. Out of scope

Not covered by this specification; deferred to follow-on capabilities or proposals:

- **Rerank protocol** — lands in a forthcoming proposal extending this capability with
  `RerankProvider` plus paired `RerankEvent` / `RerankFailedEvent` typed events.
- **Multi-modal embedding** — image embeddings, audio embeddings. Text-only in v1.
- **Per-vendor wire-format mappings.** Follow-on proposals add concrete vendor mappings (OpenAI,
  Cohere, Voyage, Jina) analogous to llm-provider §8.1 / §8.2 / §8.3.
- **Per-SDK implementation details** — httpx batching strategies, embedding-layer retry timing,
  SDK-specific error mapping. Provider-internal choices.
- **Caller-supplied determinism / seeding.** Embedding models rarely expose seeds; not v1.
- **Cross-call observability correlation** (e.g., "this rerank call used vectors from that
  embedding call"). Each call is independent at the protocol layer; any cross-call correlation
  lives in node-body code.
- **Embedding result caching at the framework level.** Caching is an application concern.
- **Streaming embeddings.** Some providers stream embeddings for very long inputs; not v1.
