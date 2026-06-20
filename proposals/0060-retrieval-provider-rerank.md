# 0060: Retrieval-Provider Rerank Protocol

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-06-09
- **Accepted:** 2026-06-20
- **Targets:** spec/retrieval-provider/spec.md (extends — adds the second protocol surface to the existing capability per the *sibling rerank protocol scoped to a forthcoming proposal* hook left by proposal 0059; restructures §3–§8 to interleave rerank sections between embedding-shape sections and shared-semantics sections — new §5 *Rerank protocol*, new §6 *Rerank response and usage shapes*, existing §5 *Error semantics* renumbers to §7, §6 *Determinism* to §8, §7 *Cross-spec touchpoints* to §9, §8 *Out of scope* to §10; extends §2 *Concepts* with rerank-side records); spec/graph-engine/spec.md (§6 — add two new typed event variants on the observer event union: `RerankEvent` and `RerankFailedEvent`, paralleling `EmbeddingEvent` + `EmbeddingFailedEvent` per the 0049 / 0058 / 0059 success+failure pairing precedent); spec/observability/spec.md (§5.5 — new §5.5.10 *Rerank provider attributes* sub-subsection for OTel mapping using OA-namespace attributes since GenAI semconv has no settled rerank coverage as of OTel semconv v1.41.1 / 2026-06-09 verification; new §5.5.11 *Typed rerank events* sub-subsection paralleling §5.5.9 for embedding; §8 — new §8.4.6 *Rerank-specific mapping* sub-subsection for Langfuse mapping onto the dedicated `Retriever` observation type, verified 2026-06-09 against current Langfuse docs as the correct shape for rerank operations; the §5.5.4 `disable_provider_payload` flag introduced by proposal 0059 already covers rerank-side payload gating with no further rename needed); plus new conformance fixtures under `spec/retrieval-provider/conformance/` and `spec/observability/conformance/`.
- **Related:** 0006 (llm-provider core — established the per-model-binding + typed-response pattern this proposal mirrors for rerank), 0049 (typed `LlmCompletionEvent` — typed-event pattern on the observer union this extends for the success-side variant), 0057 (LlmCompletionEvent field-set extension — request-side / prompt-identity / per-call disambiguator fields this proposal mirrors onto `RerankEvent` from launch rather than via a follow-on cycle), 0058 (LlmFailedEvent typed variant — failure-side typed event paired with the success-side per the success+failure pairing precedent this proposal applies), 0059 (retrieval-provider capability + embedding protocol — established the capability home, the `<domain>-provider` family framing, the `disable_provider_payload` cross-spec rename, the Langfuse dedicated-observation-type pattern this proposal extends to rerank, and the privacy posture pattern for payload-bearing provider operations)
- **Supersedes:**

## Summary

Adds `RerankProvider` as the second protocol surface on the existing `retrieval-provider`
capability (created by proposal 0059). `RerankProvider` re-scores a list of documents
against a query, returning the documents sorted by relevance with provider-specific
scores. Pairs with `EmbeddingProvider` as the two retrieval-primitive protocols sitting
under the same capability — same per-model-binding contract, same error-category
enumeration, same observer-event union pattern, same Langfuse dedicated-observation-type
mapping approach.

This proposal lands:

1. The `RerankProvider` protocol — `ready()` + `rerank(query: str, documents: list[str],
   *, top_k: int | None = None, config?) -> RerankResponse`, with typed response carrying
   the scored documents sorted by relevance descending.
2. `RerankResponse` + `RerankUsage` + `ScoredDocument` shapes — mirroring the
   `EmbeddingResponse` / `EmbeddingUsage` pattern from §4 with rerank-specific semantics
   (per-document relevance scores, optional caller-side document echo, messy usage
   surface reflecting the real provider landscape).
3. Two new typed observer events on the graph-engine §6 observer event union:
   `RerankEvent` (success) and `RerankFailedEvent` (failure). Each carries the
   identity / scoping / request-side field set established by `EmbeddingEvent` from
   proposal 0059 (which itself mirrored `LlmCompletionEvent` post-0057), plus
   rerank-specific success-side or failure-specific fields.
4. OTel mapping for rerank spans — OA-namespace `openarmature.rerank.*` attributes only,
   since the upstream OTel GenAI semantic conventions have no settled rerank coverage as
   of OTel semconv v1.41.1 (verified 2026-06-09 against `docs/compatibility.md`'s OTel
   semconv entry). A follow-on proposal MAY adopt `gen_ai.operation.name = "rerank"`
   (or whatever upstream lands) when the upstream attribute reaches Stable.
5. Langfuse mapping for rerank observations using Langfuse's dedicated `Retriever`
   observation type. Verified 2026-06-09 against current Langfuse docs — `Retriever`
   is positioned for "data retrieval steps, such as a call to a vector store or a
   database," explicitly broader than vector-store-fetch and inclusive of reranking
   operations in a retrieval pipeline. Field shape (`input` carrying `{query, topK}`,
   `output` carrying retrieved documents + relevance scores, optional `model`,
   `metadata`) lines up directly with rerank's payload shape. Created via the SDK's
   `asType="retriever"` parameter (or per-language idiomatic equivalent).

The privacy posture (query + documents + result documents are payload-bearing data
gated by `disable_provider_payload`) inherits the cross-spec flag posture that
proposal 0059 established. No further cross-spec rename or flag addition is needed.

## Motivation

Three forces converge — closely parallel to 0059's motivation, with rerank-specific
notes where the picture differs.

**Observability-blind-spot for rerank calls today.** Downstream RAG pipelines doing
two-stage retrieval (embedding → first-pass candidates → rerank → top-k for the LLM
context) currently bypass OpenArmature entirely on the rerank step via direct HTTP
calls to Cohere / Voyage / Jina endpoints. Same observability hole as embedding had
pre-0059: no OTel span, no observer event, no Langfuse observation, no per-invocation
cost rollup. With embedding now observable via 0059, the rerank step is the remaining
RAG-pipeline gap.

**Per-model-binding stays load-bearing.** Same llm-provider §5 contract as the
embedding case: one provider instance, one model identifier. Rerank model identifiers
(`rerank-multilingual-v3.0`, `voyage-rerank-2`, `jina-reranker-v2-base-multilingual`)
live in disjoint namespaces from both completion and embedding identifiers. A
`RerankProvider` bound to its own model preserves the per-model-binding contract while
opening a path to observable rerank calls.

**Provider landscape variance is even sharper for rerank than for embedding.**

| Provider / runtime | complete | embed | rerank |
|---|---|---|---|
| OpenAI (hosted) | yes | yes | **no** |
| Anthropic (hosted) | yes | no | **no** |
| Cohere (hosted) | yes | yes | yes |
| Voyage AI (hosted) | no | yes | yes |
| Jina AI (hosted) | no | yes | yes |
| TEI — HuggingFace Text Embeddings Inference (self-hosted) | no | yes | yes |
| vLLM (self-hosted) | yes | partial | no |

Two of the five major hosted providers don't expose rerank at all; Jina AI is
rerank-first (and embedding-second). A unified Provider abstraction is even more
wrong for rerank than for embedding — it would force the two largest LLM-completion
providers (OpenAI + Anthropic) to stub out a method neither serves. `RerankProvider`
as a separate protocol lets each impl declare what its backend supports; downstream
pipelines configure a `RerankProvider` instance from a provider that actually does
rerank.

**Runtime-agnostic by design.** The protocol contract doesn't distinguish hosted
SaaS backends from self-hosted serving runtimes — both bind to a model identifier
per instance, both expose `ready()` + `rerank()`, both surface the same response
shape. A `RerankProvider` instance bound to `"rerank-multilingual-v3.0"` against
Cohere's hosted endpoint and a `RerankProvider` instance bound to
`"bge-reranker-base"` against a local TEI endpoint compose into a graph identically.
The pattern parallels the existing llm-provider §8.1 *OpenAI-compatible mapping*
which serves both OpenAI hosted and vLLM self-hosted backends through the same
adapter shape. Per-runtime wire-format mappings (TEI's `/rerank` endpoint, Cohere's
`/v2/rerank`, etc.) ship as follow-on proposals — see *Out of scope* below.

Type signatures stay precise as a fourth-order benefit, also paralleling 0059's
framing — `rerank()` returns `list[ScoredDocument]` (with relevance scores);
`embed()` returns `list[vector]`; `complete()` returns a structured LLM response.
A union return type or generic `query()` method would erase per-capability semantics
the type system protects today.

## Proposed change

### Extend `spec/retrieval-provider/spec.md`

The capability scaffold landed in proposal 0059. This proposal adds the second
protocol surface (rerank) alongside the existing embedding surface, restructuring
the section numbering to interleave the rerank sections between the embedding
sections and the shared-semantics sections.

#### Section restructure

| Current section | Post-0060 section | Change |
|---|---|---|
| §1 Purpose | §1 Purpose | Unchanged (light touch — adds rerank to the protocol-surface list) |
| §2 Concepts | §2 Concepts | Extended with rerank-side concepts |
| §3 EmbeddingProvider protocol | §3 EmbeddingProvider protocol | Unchanged |
| §4 EmbeddingResponse and EmbeddingUsage shapes | §4 EmbeddingResponse and EmbeddingUsage shapes | Unchanged |
| — | **§5 RerankProvider protocol** | NEW |
| — | **§6 RerankResponse, RerankUsage, ScoredDocument shapes** | NEW |
| §5 Error semantics | §7 Error semantics | Renumbered; body extended with rerank-applicable subset framing |
| §6 Determinism | §8 Determinism | Renumbered; body extended with rerank determinism notes |
| §7 Cross-spec touchpoints | §9 Cross-spec touchpoints | Renumbered; body extended with rerank touchpoints |
| §8 Out of scope | §10 Out of scope | Renumbered; body extended with rerank-side out-of-scope items |

Cross-references to retrieval-provider §5 / §6 / §7 / §8 from other specs and from
existing conformance fixtures (graph-engine §6 EmbeddingEvent / EmbeddingFailedEvent
tables; observability §5.5.8 / §8.4.5; observability fixtures 074–083;
retrieval-provider fixtures 002–005) update to §7 / §8 / §9 / §10 at Accept time.
Count of references to update: 6 distinct §5 references shift to §7 (enumerated in
the *Conformance test impact* section below).

#### §2 *Concepts* extension

The existing `RetrievalProvider` umbrella term already covers both `EmbeddingProvider`
and `RerankProvider` (per the proposal 0059 §2 text). This proposal extends the
concepts list with rerank-side records:

- **RerankProvider** — an object that, given a query string and a list of candidate
  documents, returns the documents sorted by query-relevance with provider-specific
  scores. Bound to a specific rerank model identifier per instance.
- **RerankResponse** — the result of a `rerank()` call: the sorted scored documents,
  the model identifier, usage information, and (when present) the provider-returned
  response identifier and the parsed raw response.
- **RerankUsage** — a usage record with optional `search_units` and optional
  `input_tokens`, reflecting the messy provider landscape where rerank pricing
  surfaces vary widely.
- **ScoredDocument** — a single result entry carrying the document's original index
  in the input list, the provider-assigned relevance score, and (optionally) an echo
  of the document text.
- **Rerank runtime config** — a `RuntimeConfig`-shaped record (parallel to
  llm-provider §6) carrying rerank-specific caller-supplied request parameters.
  Initially minimal: one declared field, `return_documents: bool` (default
  `False`), controlling whether the provider echoes document text on each
  `ScoredDocument` in the response. The field name + default match the major
  rerank vendors' wire-shape parameter (Cohere, Voyage AI, Jina AI all expose
  `return_documents` defaulting `False`); per-vendor wire-format mappings will pin
  the source-side translation if any vendor diverges. When `False`, providers
  return `index` + `relevance_score` only; when `True`, providers also echo the
  document text. Plus the extras-pass-through bag for vendor-specific knobs.

#### §5 *RerankProvider protocol* (NEW)

Section structure mirrors §3 *EmbeddingProvider protocol*:

##### `ready()`

A no-argument async operation that verifies the provider can serve requests against
the bound model. Same idempotency + error-surfacing contract as §3's `ready()`:

- MUST be idempotent.
- MUST surface `provider_invalid_model` (per §7) if the bound rerank model is not
  recognized by the backend.
- MUST surface `provider_model_not_loaded` (per §7) if the bound model is recognized
  but not currently usable.
- MAY raise other §7 error categories under the same conditions as §3's `ready()`.

##### `rerank(query, documents, *, top_k=None, config=None)`

The rerank operation. Parameters:

| Parameter | Type | Description |
|---|---|---|
| `query` | string | The query string the documents are scored against. MUST be non-empty; an empty query raises `provider_invalid_request` (§7) at the pre-send validation layer. |
| `documents` | list of strings | The candidate documents to score against the query. MUST be a list (even single-document callers wrap as a one-element list — matches the embedding protocol's "always a list" framing). MUST be non-empty; an empty document list raises `provider_invalid_request` (§7). |
| `top_k` | optional int (keyword-only) | The maximum number of results the caller wants returned. `None` means "all" (provider may return up to `len(documents)` results). MUST be positive when supplied; zero or negative raises `provider_invalid_request` (§7). MAY exceed `len(documents)` — the provider returns at most `len(documents)` results regardless. |
| `config` | optional `RerankRuntimeConfig` (keyword-only) | Caller-supplied rerank runtime config. |

Returns a `RerankResponse` (§6).

The `rerank()` operation:

- MUST be stateless. Repeated calls with the same `query` / `documents` / `top_k` /
  `config` MUST NOT change observable provider state.
- MUST raise one of the §7 error categories on failure.
- MUST return results sorted by `relevance_score` descending (most relevant first).
- MUST preserve each result's `index` field as the position in the *input* documents
  list, so callers can map sorted results back to their original documents.
- MUST NOT loop, retry, or fall back. Pipeline-utilities §6 middleware and per-call
  retry compose above the provider.

##### Per-instance model binding

Per-instance model binding follows the llm-provider §5 contract exactly, identical to
the embedding protocol's framing in §3. Implementations bind one rerank model
identifier per provider instance via a constructor parameter (or per-language
idiomatic equivalent). The bound identifier is visible to the observability layer
(per observability §5.5) as the `gen_ai.request.model` attribute on the rerank span.

#### §6 *RerankResponse, RerankUsage, ScoredDocument shapes* (NEW)

##### RerankResponse

| Field | Description |
|---|---|
| `results` | List of `ScoredDocument` entries sorted by `relevance_score` descending (most relevant first). `len(results)` is at most `min(top_k, len(documents))` when `top_k` is supplied; at most `len(documents)` otherwise. MAY be shorter than that bound if the provider returns fewer results (e.g., relevance-threshold filtering on the provider side). |
| `model` | The model identifier the provider returned. MAY be a more specific identifier than the one the provider was bound against. |
| `usage` | A `RerankUsage` record (defined below). |
| `response_id` | The provider-returned response identifier when present; null otherwise. Matches the OTel GenAI semconv `gen_ai.response.id` attribute (per observability §5.5.10) and the typed `RerankEvent.response_id` field (per graph-engine §6). |
| `raw` | The parsed provider response, as a language-idiomatic representation of deserialized JSON (Python: `dict[str, Any]`; TypeScript: `Record<string, unknown>`). MUST be populated on every successful return. Per charter §3.1 principle 8 ("Transparency over abstraction") — callers retain access to provider-specific fields the normalized shape doesn't surface (provider-specific score-calibration metadata, vendor extensions, etc.). Parallel to llm-provider §6 `Response.raw` and retrieval-provider §4 `EmbeddingResponse.raw`. |

##### ScoredDocument

| Field | Description |
|---|---|
| `index` | Int. The 0-based position of this document in the original input `documents` list. **Load-bearing for caller-side lookup** — callers MUST be able to map a result back to its input document via `documents[result.index]`. Implementations MUST preserve this verbatim from the provider response. |
| `relevance_score` | Float. The provider-assigned relevance score; higher = more relevant. **Provider-specific scale** — most providers normalize to `[0.0, 1.0]` but the spec does NOT pin a scale. Cross-provider score comparisons are NOT meaningful. |
| `document` | The echoed document text when the provider returns it; null otherwise. Implementations MUST surface the provider's echo verbatim when present; MUST NOT fabricate the echo from the input `documents` list when the provider omits it (the provider's echo and the caller's input are two different surfaces; conflating them would mask provider-side document transformations like deduplication or truncation). |

##### RerankUsage

| Field | Description |
|---|---|
| `search_units` | Int or null. The provider-reported count of "search units" billed for this call. Populated for Cohere; absent or null for providers that don't surface it. |
| `input_tokens` | Int or null. The provider-reported count of input tokens (query + concatenated documents). Populated for some providers (e.g., Voyage AI); absent or null for others. |

Both fields default to null. Implementations MUST populate the field when the
provider returns a corresponding value and MUST NOT fabricate one when the provider
omits it. A `RerankUsage` with both fields null is valid and represents the
"provider reports no billing surface" case.

##### Cross-impl invariants

- `results` are sorted by `relevance_score` descending. Implementations that receive
  an unsorted provider response MUST sort before returning (some provider SDKs
  pre-sort; some don't).
- Each result's `index` MUST be a valid index into the input `documents` list
  (`0 <= index < len(documents)`). Implementations MUST raise
  `provider_invalid_response` (§7) when the provider returns an out-of-range index.
- The same `index` MUST NOT appear twice in `results`. Implementations MUST raise
  `provider_invalid_response` (§7) on duplicate-index responses.
- When `top_k` is supplied, `len(results) <= top_k`. Implementations MUST raise
  `provider_invalid_response` (§7) if the provider returns more results than
  requested.
- When the provider returns `document` echoes for some results but not others,
  implementations MUST preserve the per-result variance (null where the provider
  omitted; populated where the provider echoed). MUST NOT auto-fill from the input
  documents list.

#### §7 *Error semantics* (renumbered from §5; extended)

The shared error-category enumeration covers both embedding and rerank. The
rerank-applicable subset (the §7 categories minus the LLM-completion-specific ones
and minus `provider_unsupported_content_block` which is text-block-specific):

- `provider_authentication`, `provider_unavailable`, `provider_invalid_model`,
  `provider_model_not_loaded`, `provider_rate_limit`, `provider_invalid_response`,
  `provider_invalid_request` — all apply
- `provider_unsupported_content_block` — does NOT apply (rerank takes strings, not
  content blocks)
- `structured_output_invalid` — does NOT apply (rerank has no `response_schema`)

Pre-send validation categories for `provider_invalid_request`:

- Empty `query` string
- Empty `documents` list
- `top_k <= 0`

The exception-flow contract from llm-provider §7 applies identically.

#### §8 *Determinism* (renumbered from §6; extended)

Rerank model determinism guarantees are similar to embedding's: providers MAY return
slightly different scores for the same `(query, documents)` pair across calls
(model-version updates, server-side non-determinism, etc.). This specification MUST
NOT assume bit-identical responses for equivalent inputs.

A stronger property worth noting: even when scores are identical bit-for-bit, the
*ranking order* MUST be stable for a given provider's documented determinism
guarantees. Two documents with identical scores MAY appear in either order across
calls (provider implementation detail) unless the provider documents a tie-breaking
rule. The spec MUST NOT assume one.

#### §9 *Cross-spec touchpoints* (renumbered from §7; extended)

- **graph-engine §6** — typed observer events `RerankEvent` (success) and
  `RerankFailedEvent` (failure), paralleling the embedding-side pair from proposal
  0059.
- **observability §5.5** — OTel mapping for rerank spans (OA-namespace
  `openarmature.rerank.*` attributes; no Stable GenAI semconv subset since upstream
  has no rerank coverage as of v0.54.0; span name `openarmature.rerank.complete`
  discriminates the operation).
- **observability §8** — Langfuse mapping using Langfuse's dedicated `Retriever`
  observation type (verified 2026-06-09 as the correct shape for rerank operations).
- **observability §5.5.4** — observer-level privacy flag `disable_provider_payload`
  (renamed from `disable_llm_payload` by proposal 0059) gates payload from any
  provider call, including rerank payload (query + documents + result document
  echoes).
- **llm-provider §7** — error-category enumeration (inherited).
- **pipeline-utilities §6 (middleware)** — `RerankProvider` calls are eligible for
  retry middleware identically to `complete()` and `embed()` calls.

#### §10 *Out of scope* (renumbered from §8; extended)

Inherits the existing §8 list (multi-modal embedding, per-vendor wire formats, etc.)
and adds rerank-specific entries:

- **Per-vendor and per-runtime wire-format mappings.** Follow-on proposals add
  Cohere / Voyage / Jina (hosted SaaS) and TEI (self-hosted HuggingFace serving
  runtime) mappings analogous to llm-provider §8.1 / §8.2 / §8.3 once a need
  surfaces. (Note: OpenAI doesn't offer rerank as of v0.54.0; vLLM doesn't either.
  The relevant rerank wire mappings to land first are Cohere / TEI / Voyage / Jina,
  in approximate order of downstream demand.)
- **Cross-call observability correlation between embedding and rerank.** E.g., "this
  rerank call used vectors from that embedding call." Each call is independent at
  the protocol layer.
- **Multi-modal rerank.** Image documents, audio documents, etc. Text-only in v1.
- **Caller-supplied determinism / seeding.** Rerank models rarely expose seeds.
- **Streaming rerank.** Some providers stream large result sets; not v1.
- **Score normalization across providers.** Each provider's relevance scale is
  surfaced as-returned; the spec does NOT define a normalization layer. Applications
  needing cross-provider score comparison build their own normalization.

### Extend graph-engine §6 with `RerankEvent` + `RerankFailedEvent`

Two new typed event variants on the observer event union (the fifth and sixth typed
variants after `LlmCompletionEvent`, `LlmFailedEvent`, `EmbeddingEvent`,
`EmbeddingFailedEvent`). Paired from launch per the 0049 → 0058 → 0059 success+failure
pairing precedent.

#### `RerankEvent` (success)

Mirrors `EmbeddingEvent`'s identity / scoping / request-side field set with
rerank-specific substitutions:

| Field | Type | Description |
|---|---|---|
| `invocation_id` | string | The outer invocation's identifier, per observability §5.1. |
| `correlation_id` | string \| null | Cross-backend correlation ID, per observability §3.1. |
| `node_name` | string | The user-defined node that issued the call. |
| `namespace` | sequence of strings | The calling node's namespace. |
| `attempt_index` | int | The retry-attempt index (0 on the first attempt). |
| `fan_out_index` | int \| null | Per pipeline-utilities §9. Null otherwise. |
| `branch_name` | string \| null | Per pipeline-utilities §11. Null otherwise. |
| `provider` | string | The rerank provider identifier (matches `gen_ai.system` per observability §5.5.3). |
| `model` | string | The model identifier the request was made against. |
| `response_model` | string \| null | The model identifier the provider returned. |
| `response_id` | string \| null | The provider-returned response identifier when present. |
| `usage` | record \| null | `RerankUsage` record per retrieval-provider §6. |
| `latency_ms` | float \| null | Wall-clock latency of the rerank call measured at the adapter boundary. |
| `caller_invocation_metadata` | mapping \| null | OPTIONAL field; same opt-in semantics as on `EmbeddingEvent`. |
| `query` | string | The query string the rerank call was made with. Populated unconditionally; observer-side privacy gating at the rendering boundary per the privacy paragraph below. |
| `documents` | list of string | The input documents list. Populated unconditionally; same privacy posture as `query`. |
| `request_params` | mapping | Rerank-specific runtime-config fields the caller supplied (initially `return_documents` per retrieval-provider §2). Absence-is-meaningful semantics. Empty mapping when no parameters were supplied. |
| `request_extras` | mapping | The rerank runtime config's extras pass-through bag. Same shape and privacy posture as on `EmbeddingEvent`. |
| `active_prompt` | record \| null | Snapshot of the active `Prompt` identity at rerank-call time. Same shape as on `EmbeddingEvent`. |
| `active_prompt_group` | record \| null | Snapshot of the active `PromptGroup` identity. Same shape. |
| `call_id` | string | A per-call disambiguator minted by the implementation. **Always present** (never null); freshly minted per `rerank()` call. |
| `document_count` | int | The number of input documents the call was made with (equals `len(documents)`). Derivable but kept for ergonomics + cross-vendor consistency. |
| `top_k` | int \| null | The caller-supplied `top_k` value (or null if the caller passed `None`). |
| `result_count` | int | The number of `ScoredDocument` entries the provider returned (equals `len(response.results)`). |

#### `RerankFailedEvent` (failure)

Mirrors `RerankEvent`'s identity / scoping / request-side field set 1:1 with the
success-only fields (`response_id`, `response_model`, `usage`, `result_count`) absent
and the same three failure-specific fields from `LlmFailedEvent` / `EmbeddingFailedEvent`:

| Field | Type | Description |
|---|---|---|
| `invocation_id` | string | The outer invocation's identifier, per observability §5.1. |
| `correlation_id` | string \| null | Cross-backend correlation ID, per observability §3.1. |
| `node_name` | string | The user-defined node that issued the call. |
| `namespace` | sequence of strings | The calling node's namespace. |
| `attempt_index` | int | The retry-attempt index (0 on the first attempt). |
| `fan_out_index` | int \| null | Per pipeline-utilities §9. Null otherwise. |
| `branch_name` | string \| null | Per pipeline-utilities §11. Null otherwise. |
| `provider` | string | The rerank provider identifier. |
| `model` | string | The model identifier the request was made against. |
| `latency_ms` | float \| null | Wall-clock latency from `rerank()` entry to the point the failure was raised. May be null when latency is not measured. |
| `caller_invocation_metadata` | mapping \| null | OPTIONAL field; same opt-in semantics as on `RerankEvent`. |
| `query` | string | The query string. Populated unconditionally; same observer-side privacy-gating posture as on `RerankEvent`. |
| `documents` | list of string | The input documents list. Populated unconditionally; same privacy posture. |
| `request_params` | mapping | Rerank-specific config fields the caller supplied. Same shape as on `RerankEvent`. |
| `request_extras` | mapping | The rerank runtime config's extras pass-through bag. Same shape and privacy posture as on `RerankEvent`. |
| `active_prompt` | record \| null | Snapshot of the active `Prompt` identity at rerank-call time. Same shape as on `RerankEvent`. |
| `active_prompt_group` | record \| null | Snapshot of the active `PromptGroup` identity. Same shape. |
| `call_id` | string | A per-call disambiguator minted by the implementation. **Always present**; freshly minted per `rerank()` call. A failed call gets its own `call_id`, distinct from any retry-attempt sibling. |
| `document_count` | int | The number of input documents the call was made with (equals `len(documents)`). |
| `top_k` | int \| null | The caller-supplied `top_k` value (or null if the caller passed `None`). |
| `error_category` | string | One of the llm-provider §7 normative categories applicable to rerank (per retrieval-provider §7). Always present. |
| `error_type` | string \| null | OPTIONAL impl-level / vendor-specific error type or code. Two acceptable styles (vendor error code, upstream exception class name). Null when no impl-side type is available. |
| `error_message` | string | Human-readable message from the raised exception. Always present (empty string when the exception carried no message). |

Success-only fields absent from the failure variant: `response_id`, `response_model`,
`usage`, `result_count` — no response was received.

#### Mutual exclusion + exception-flow + dispatch timing

Same rules as the 0058 / 0059 pairs: `RerankEvent` and `RerankFailedEvent` are
mutually exclusive on a given `rerank()` call; implementations MUST NOT emit both.
The §7 category exception still raises out of `rerank()`; the typed event is
dispatched alongside the exception, not in place of it. Both events MUST be
dispatched on the observer delivery queue at the point of `rerank()` completion or
failure (after success / after exception is raised; before the call returns or
re-raises to the caller). Delivery semantics follow graph-engine §6 — strict-serial
across the invocation, async-delivered.

#### Privacy posture

`query`, `documents`, and `request_extras` carry potentially sensitive payload data
(RAG-pipeline indexing of user-supplied content). The privacy posture is identical
to `EmbeddingEvent`'s — observer-side gating at the rendering boundary per
observability §5.5.4 (implementations populate the fields unconditionally; observers
honor `disable_provider_payload`). The `ScoredDocument.document` echoes in the
response are payload-bearing on the same footing (gated by the same flag).

The vec2text-aware framing from proposal 0059 doesn't directly apply to rerank
(no vectors), but the underlying privacy concern is the same — query and document
text accumulated in traces represent a corpus-leakage surface for RAG applications.
Default-suppression is the conservative posture.

### Extend observability §5.5 (OTel) with rerank mapping

A new §5.5.10 *Rerank provider attributes* sub-subsection paralleling the existing
§5.5.8 *Embedding provider attributes* block (introduced by proposal 0059). Numbers
assume nothing else lands in §5.5 between v0.54.0 and this proposal's Accept; if
intervening proposals shift the available slot, the Accept PR renumbers accordingly.

**Span name** — `openarmature.rerank.complete` (parallel to the existing
`openarmature.embedding.complete` and `openarmature.llm.complete` span names).

**No Stable GenAI semconv subset** — the upstream OTel GenAI semantic conventions
have no rerank coverage as of OTel semconv v1.41.1 (verified 2026-06-09 per
`docs/compatibility.md`'s OTel semconv entry). Only `gen_ai.system`,
`gen_ai.request.model`, and `gen_ai.usage.input_tokens` are applicable in the
abstract, and the latter is rerank-side-conditional. The applicable subset that
still maps cleanly:

- `gen_ai.system` ← `RerankProvider`'s configured provider identifier. For hosted
  SaaS backends, the vendor name (`"cohere"`, `"voyageai"`, `"jina"`). For
  self-hosted serving runtimes, the runtime identifier (`"tei"` for HuggingFace
  Text Embeddings Inference, etc.) — parallel to how the bundled OpenAI-compatible
  LLM adapter against vLLM uses `"vllm"` as the system value rather than the
  backing model's organization. Convention: identify the wire-protocol surface the
  adapter speaks to, not the underlying model's developer.
- `gen_ai.request.model` ← bound rerank model identifier
- `gen_ai.response.model` ← `RerankResponse.model` (provider-echoed)
- `gen_ai.response.id` ← `RerankResponse.response_id` (when present)
- `gen_ai.usage.input_tokens` ← `RerankResponse.usage.input_tokens` (when populated)

`gen_ai.usage.input_tokens` follows the OA conditional-emission convention (per the
§5.5.8 embedding mapping and the 0047 cache-attribute precedent): the attribute is
emitted only when `RerankResponse.usage.input_tokens` is non-null, and omitted
entirely otherwise. Unlike the embedding span — where `input_tokens` is always
present — rerank providers vary on whether they report a token count (Voyage AI
does; Cohere reports search-units instead), so the attribute genuinely exercises
the conditional branch.

A follow-on proposal MAY add `gen_ai.operation.name = "rerank"` (or whatever
operation discriminator upstream lands) when the upstream attribute reaches Stable
and a rerank-applicable well-known value is documented, per the §5.5.3.1 / 0047
mirror pattern. Operation discrimination is via the span name + provider for now.

**OA-namespace attributes**:

| Attribute | Type | Description |
|---|---|---|
| `openarmature.rerank.query_length` | int | The byte length of the query string (UTF-8 encoded). Not a token count — `gen_ai.usage.input_tokens` carries that when the provider reports it. |
| `openarmature.rerank.document_count` | int | The number of input documents. |
| `openarmature.rerank.top_k` | int | The caller-supplied `top_k` value when supplied; omitted from the attribute set when the caller passed `None`. |
| `openarmature.rerank.result_count` | int | The number of `ScoredDocument` entries the provider returned. |
| `openarmature.rerank.search_units` | int | The provider-reported search-units billed for this call (sourced from `RerankResponse.usage.search_units`). Conditionally emitted: populated only when the source field is non-null. Flat namespace matches §5.5.8's `openarmature.embedding.*` attribute convention (no `.usage.` infix). |
| `openarmature.rerank.query` | string | The query string. Subject to `disable_provider_payload` (§5.5.4) and the §5.5.5 truncation contract. |
| `openarmature.rerank.documents` | string (JSON-encoded list of strings) | The input documents list. Subject to `disable_provider_payload`. |
| `openarmature.rerank.results` | string (JSON-encoded list of records) | The scored results (each record carrying `index` + `relevance_score` + optional `document` echo). Subject to `disable_provider_payload`. |

**Opt-out flags.** The `disable_provider_payload` and `disable_genai_semconv` flags
from §5.5.4 apply analogously to rerank spans (same posture as §5.5.8 embedding
documents). The `disable_llm_spans` flag is scoped to LLM completion spans only
(per the §5.5.8 framing already documenting this).

**Truncation.** The §5.5.5 truncation contract applies identically to the rerank
payload attributes.

A new §5.5.11 *Typed rerank events* sub-subsection frames the `RerankEvent` +
`RerankFailedEvent` typed-event surface as the structured form of the rerank
attribute surface, paralleling §5.5.9 for embedding events.

### Extend observability §8 (Langfuse) with rerank mapping

A new §8.4.6 *Rerank-specific mapping* sub-subsection (after §8.4.5
embedding-specific mapping from proposal 0059).

Rerank calls map onto Langfuse's dedicated **`Retriever`** observation type —
verified 2026-06-09 against current Langfuse docs. `Retriever` is positioned for
"data retrieval steps, such as a call to a vector store or a database," explicitly
broader than vector-store-fetch and inclusive of reranking when it's part of the
retrieval pipeline. The field shape matches rerank's payload directly:

- `input` carries `{query, topK, ...}` — exactly the rerank request shape
- `output` carries retrieved documents + relevance scores — exactly the rerank
  response shape
- `model` (optional) — the rerank model identifier
- `metadata` — OA-namespace context fields

Created via the SDK's `asType="retriever"` parameter (or per-language idiomatic
equivalent — Python `@observe(as_type="retriever")` decorator or
`start_observation(as_type="retriever")`; TypeScript `startObservation(..., {
asType: "retriever" })`).

Field mappings:

| Retriever observation field | Source |
|---|---|
| `retriever.model` | `RerankResponse.model`. |
| `retriever.input` | The query + documents list, serialized as `{query: "...", documents: [...]}`. Privacy-gated per `disable_provider_payload`. When the flag is `True` (default), this field is NOT populated. |
| `retriever.output` | The scored results list (each entry as `{index, relevance_score, document?}`). Privacy-gated per `disable_provider_payload`. |
| `retriever.usageDetails.input` | `RerankResponse.usage.input_tokens` when populated. |
| `retriever.usageDetails.searchUnits` | `RerankResponse.usage.search_units` when populated. Note: Langfuse's `usageDetails` is an open-shape mapping; the spec defines the OA convention for the rerank-specific `searchUnits` key here. |
| `retriever.metadata.openarmature_query_length` | The byte length of the query. |
| `retriever.metadata.openarmature_document_count` | The input documents count. |
| `retriever.metadata.openarmature_top_k` | The caller-supplied `top_k` when supplied; omitted otherwise. |
| `retriever.metadata.openarmature_result_count` | The returned results count. |
| `retriever.metadata.openarmature_response_id` | `RerankResponse.response_id` when present. |

**Privacy posture for rerank observations.** Query, input documents, and result
document echoes are all payload-bearing data, gated by `disable_provider_payload`
(default `True` per §5.5.4). When the flag is `True`, the `Retriever` observation
populates `model` + `usageDetails` + identity metadata only; `input` and `output`
are NOT populated. When `False`, both fields populate fully.

**Trace-level cost rollup.** Langfuse's trace-level cost aggregation handles
`Generation` + `Embedding` + `Retriever` observations uniformly via the
per-observation `usageDetails` field. The OA convention adds `searchUnits` to the
`usageDetails` shape for rerank; Langfuse's open `usageDetails` mapping permits the
extension. Costs from rerank calls roll into the same `trace.totalCost` aggregation
as LLM completion and embedding costs.

## Conformance test impact

### New fixtures under `spec/retrieval-provider/conformance/`

Seven protocol-level fixtures paralleling the embedding fixtures (001-005):

1. **`006-rerank-positive-control`** — Bound `RerankProvider` with a mocked provider
   that returns 3 scored documents for 3 input documents. Asserts response shape:
   results sorted by `relevance_score` descending, each `index` is a valid index
   into input documents, `usage.search_units` populated, `response_id` populated.
2. **`007-rerank-model-binding-error`** — `RerankProvider` instantiated with an
   unknown model id; `ready()` raises `provider_invalid_model`.
3. **`008-rerank-malformed-response-out-of-range-index`** — Provider returns a
   result with `index` outside `[0, len(documents))`; `rerank()` raises
   `provider_invalid_response` per §7.
4. **`009-rerank-malformed-response-duplicate-index`** — Provider returns two
   results with the same `index`; `rerank()` raises `provider_invalid_response`.
5. **`010-rerank-top-k-respected`** — Multi-case fixture covering the `top_k`
   contract surface end-to-end:
   - **Case A** (`top_k_exact`): caller supplies `top_k=2`; provider returns 2
     results; passes through. Positive control.
   - **Case B** (`top_k_undershot`): caller supplies `top_k=3`; provider returns 2
     results (provider-side relevance filtering reduced the result set); passes
     through. Provider returning fewer than requested is permitted.
   - **Case C** (`top_k_larger_than_documents`): caller supplies `top_k=10`,
     `documents` has 3 entries; provider returns 3 results; passes through. `top_k`
     exceeding `len(documents)` is permitted and the protocol contract holds.
6. **`011-rerank-top-k-violation`** — Caller supplies `top_k=2`; provider returns 3
   results; the adapter MUST raise `provider_invalid_response` (cross-impl invariant
   violated). Negative control split out from `010` so the positive-control fixture
   stays a single-axis pass-through assertion.
7. **`012-rerank-per-result-echo-variance`** — Cross-impl invariant for the
   `ScoredDocument.document` echo field: provider returns 3 results where two have
   `document` populated and one has `document` absent; adapter MUST preserve the
   per-result variance (null where the provider omitted; populated where the
   provider echoed). MUST NOT auto-fill from the input `documents` list. Locks
   down the §6 cross-impl invariant against fabrication.

### New fixtures under `spec/observability/conformance/`

Tentatively numbered 084-093 (after the 074-083 embedding fixtures from proposal
0059); final numbers assigned at Accept. Ten fixtures paralleling the embedding-side
074-083 set:

- **`084-rerank-event-dispatch`** — Successful `rerank()` call dispatches
  `RerankEvent` with the full field set populated.
- **`085-rerank-failure-event-dispatch-on-provider-unavailable`** — Failed
  `rerank()` call dispatches `RerankFailedEvent`; exception still raises.
- **`086-rerank-event-mutual-exclusion`** — Successful call emits exactly one
  `RerankEvent` and zero `RerankFailedEvent`; failed call emits exactly one
  `RerankFailedEvent` and zero `RerankEvent`.
- **`087-rerank-event-call-id-distinct`** — Multiple `rerank()` calls in an
  invocation emit `RerankEvent`s with distinct `call_id` values.
- **`088-rerank-event-query-and-documents-populated`** — `query` and `documents`
  fields carry the input verbatim.
- **`089-rerank-event-request-params-populated`** — `request_params` carries
  `return_documents` when supplied; absence-is-meaningful for other params.
- **`090-rerank-event-top-k-and-result-count-populated`** — `top_k` matches the
  caller-supplied value (or null when caller passed `None`); `result_count` matches
  the response.
- **`091-rerank-event-active-prompt-populated`** — Rerank call inside a prompt-
  context binding carries `active_prompt` snapshot.
- **`092-otel-rerank-span-attributes`** — OTel span emitted with span name
  `openarmature.rerank.complete` and the OA-namespace rerank attributes plus the
  applicable Stable GenAI semconv subset.
- **`093-langfuse-rerank-observation`** — Langfuse `Retriever` observation (created
  via `asType="retriever"`), with `model` + `usageDetails` + identity metadata
  populated. Asserts the observation type is `retriever` (not `generation` or
  generic `span`). Two cases: payload-suppressed by default; payload-emitted when
  `disable_provider_payload=False`.

### Cross-reference updates at Accept

The retrieval-provider §-renumbering shifts §5/§6/§7/§8 → §7/§8/§9/§10. Cross-
reference updates needed:

- `spec/graph-engine/spec.md` — 2 references (lines around the EmbeddingEvent /
  EmbeddingFailedEvent tables): retrieval-provider §5 (error categories) → §7;
  retrieval-provider §4 (EmbeddingResponse shape) stays at §4.
- `spec/observability/spec.md` §8.4.5 — 1 reference: retrieval-provider §4 stays
  at §4 (no shift needed; the embedding-section §4 is unchanged).
- `spec/observability/conformance/075-embedding-failure-event-dispatch-on-provider-unavailable.md`
  — 1 reference: retrieval-provider §5 (error category) → §7.
- `spec/observability/conformance/079-embedding-event-request-params-populated.md`
  — 1 reference: retrieval-provider §2 stays at §2.
- `spec/retrieval-provider/conformance/002-embed-model-binding-error.md` — 1
  reference: retrieval-provider §5 (error category) → §7.
- `spec/retrieval-provider/conformance/003-embed-malformed-response-mismatched-vector-count.md`
  — 1 reference: §5 → §7.
- `spec/retrieval-provider/conformance/004-embed-malformed-response-inconsistent-dimensions.md`
  — 1 reference: §5 → §7.

Net cross-reference impact at Accept: 6 distinct §5 references update to §7
(graph-engine: 2; observability fixture 075: 1; retrieval-provider fixtures 002 /
003 / 004: 3). References to §2 / §3 / §4 are stable.

## Versioning

**MINOR bump** (pre-1.0). On acceptance:

- New protocol surface on existing `retrieval-provider` capability — purely
  additive at the capability level
- Two new typed event variants on the graph-engine §6 observer event union —
  `RerankEvent`, `RerankFailedEvent` (additive)
- New §5.5.10 (OTel rerank attributes) + §5.5.11 (typed rerank events) + §8.4.6 (Langfuse rerank-specific mapping) subsections in observability spec (additive)
- Section renumbering within retrieval-provider spec (existing §5–§8 shift to
  §7–§10; documented above; 6 cross-reference updates land in the same Accept
  PR for internal consistency)
- 7 fixtures under `spec/retrieval-provider/conformance/` (numbered 006-012,
  appending to the existing 001-005 embedding fixture set) + 10 fixtures under
  `spec/observability/conformance/` (numbered 084-093, appending to the existing
  074-083 embedding fixture set)

Tentative spec version target deferred to Accept. No flag rename or other breaking change
needed (the cross-spec rename infrastructure from proposal 0059 already covers
rerank's privacy posture).

## Alternatives considered

1. **Defer rerank indefinitely; let downstreams keep direct-httpx-ing.** Reject —
   same observability-blind-spot argument as proposal 0059 for embedding. Rerank
   completes the RAG-pipeline observability picture; without it, two-stage
   retrieval (embedding → rerank → LLM context) has the rerank step bypassing OA
   entirely. The 0059 work is half a story without 0060.

2. **Add `rerank()` to the existing `EmbeddingProvider` protocol.** Reject —
   different per-model-binding identity. Rerank models live in their own namespace
   distinct from embedding models; an `EmbeddingProvider` instance bound to a
   specific embedding model can't simultaneously bind to a rerank model. The
   per-model-binding contract from llm-provider §5 (inherited by retrieval-provider
   §3) is load-bearing.

3. **Spin rerank out as its own `rerank-provider` capability.** Reject — over-
   fragmentation. Embedding and rerank are both retrieval primitives; keeping them
   under one `retrieval-provider` capability with two protocol surfaces matches
   the proposal 0059 decision (alternative 6 in 0059's *Alternatives considered*)
   and parallels how `harness` is one capability with per-harness-type sub-specs.
   Splitting now would orphan the framing 0059 established.

4. **Bundle rerank into proposal 0059 as one omnibus retrieval-primitives
   proposal.** Reject — embedding shipped first by design. Bundling would have
   widened 0059's surface and delayed embedding shipping while rerank design
   questions resolved (Langfuse observation type, rerank-side usage shape, top_k
   semantics, etc.). Sequential shipping let 0059 land clean; 0060 picks up the
   rerank-specific design surface without re-litigating the capability-home or
   typed-event-pairing questions that 0059 already settled.

5. **Define rerank with a generic `query(input) -> output` shape parameterized by
   the operation type.** Reject — erases per-capability semantics the type system
   protects. `embed()` returning vectors and `rerank()` returning scored documents
   are structurally different; a generic `query()` method forces callers to
   discriminate at call sites and forces type signatures into `Any` territory.

6. **Map rerank onto Langfuse's `Generation` observation type with
   `metadata.operation = "rerank"`.** Reject — Generation is LLM-completion-shaped
   (input messages, output text, finish_reason, token usage). Rerank has none of
   those; the shape mismatch would force every Generation-consuming Langfuse
   integration to special-case rerank observations. Verified against current
   Langfuse docs (2026-06-09) that the dedicated `Retriever` type is the correct
   shape — its field surface matches rerank directly (input `{query, topK}`;
   output documents + scores; optional model; metadata).

7. **Define `top_k` on the protocol but require providers to always return exactly
   `top_k` results (padding with low-score placeholders if needed).** Reject —
   no real provider behaves this way. Cohere / Voyage / Jina all return fewer than
   `top_k` when fewer documents have non-trivial relevance scores; requiring the
   adapter to fabricate placeholders would create a per-implementation shim that
   diverges from the wire shape and misleads callers about what the provider
   actually returned. The spec contract is `len(results) <= top_k`; callers handle
   the variable-length case.

8. **Pin a normative `relevance_score` scale (e.g., `[0.0, 1.0]`) and require
   adapters to normalize provider-specific scores.** Reject — providers' scoring
   semantics differ in ways that don't translate cleanly across providers (some
   are calibrated probabilities, some are uncalibrated logits, some are
   transformer attention scores). A normative scale would force the spec to pin a
   normalization algorithm that has no obvious right answer. Callers needing
   cross-provider score comparison build their own normalization layer; the spec
   surfaces provider scores as-returned.

9. **Define `ScoredDocument.document` as REQUIRED — always populate the echo from
   the input documents list when the provider omits it.** Reject — conflates two
   different surfaces (provider's echo vs caller's input). Some providers transform
   documents server-side (deduplication, truncation, normalization); the
   transformation is observable via the echo when present and silenced when
   absent. Fabricating the echo from input documents would mask that signal. The
   spec preserves provider behavior; callers needing the input document lookup
   use `index` against their own `documents` list.

## Open questions

None remaining at draft time. The three questions surfaced during drafting are all
resolved in the proposal text above (collected in the *Resolved at Draft* block
below for retrieval). This matches proposal 0059's posture — the retrieval-provider
design surface is well-trodden after the embedding pass, so 0060's design space is
mostly settled by precedent.

**Resolved at Draft (folded into the proposal text above):**

- **Langfuse `Retriever` observation type's semantics.** Verified 2026-06-09
  against current Langfuse docs: `Retriever` is positioned for "data retrieval
  steps, such as a call to a vector store or a database," explicitly broader than
  vector-store-fetch and inclusive of reranking. Field shape (`input` carrying
  `{query, topK}`, `output` carrying retrieved documents + relevance scores,
  optional `model`, `metadata`) matches rerank's payload directly. Created via
  `asType="retriever"`. No fallback to generic `Span` needed.
- **`gen_ai.usage.input_tokens` conditional emission.** Settled by the OA
  conditional-emission convention (the §5.5.8 embedding mapping + the 0047
  cache-attribute precedent): emit when `RerankResponse.usage.input_tokens` is
  non-null, omit otherwise. Stated normatively in the §5.5.10 OTel mapping above.
  Not a genuine open question — the convention already covers it; the rerank case
  just exercises the conditional branch more often than embedding (where the field
  is always present).
- **Per-vendor `response_id` source field.** Not a protocol-level open question —
  the §6 `RerankResponse.response_id` field is fully specified (nullable;
  populated when the provider returns a response identifier, null otherwise). The
  wire position the identifier is sourced from varies per vendor and is pinned in
  each per-vendor wire-format mapping proposal (the *Per-vendor and per-runtime
  wire-format mappings* out-of-scope item below). No specific per-vendor wire
  positions are asserted in this proposal's normative text — that sourcing is
  wire-mapping-proposal territory and gets verified there.

## Out of scope

- **Per-vendor and per-runtime wire-format mappings** (Cohere / Voyage / Jina
  hosted; TEI self-hosted; any future vendors / runtimes) — follow-on proposals
  analogous to llm-provider §8.1 / §8.2 / §8.3. The protocol contract here is
  runtime-agnostic; concrete wire mappings land separately. Each mapping pins the
  per-vendor wire sourcing for fields the protocol leaves position-agnostic (e.g.,
  where `response_id` is surfaced in that vendor's response shape).
- **Cross-call observability correlation** (embedding → rerank linkage). Each
  call is independent at the protocol layer; any correlation lives in node-body
  code.
- **Multi-modal rerank** (image documents, audio documents, etc.). Text-only
  in v1.
- **Caller-supplied determinism / seeding.** Rerank models rarely expose seeds.
- **Streaming rerank.** Some providers stream large result sets; not v1.
- **Score normalization across providers.** Each provider's score scale is
  surfaced as-returned.
- **Hybrid retrieval (embedding + rerank in one call).** No provider exposes this
  as a single protocol-level operation; the two stages are always separate calls.
- **`gen_ai.operation.name` adoption.** Deferred per the stable-only upstream
  adoption policy; a follow-on proposal adds it when upstream reaches Stable
  with a rerank-applicable well-known value.
