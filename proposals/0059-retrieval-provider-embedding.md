# 0059: Retrieval-Provider Capability (Embedding Protocol)

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-06-08
- **Accepted:**
- **Targets:** spec/retrieval-provider/spec.md (creates — new capability defining the protocol shape for non-LLM-completion provider operations; this proposal lands the capability scaffold + the `EmbeddingProvider` protocol as the first protocol surface; sibling rerank protocol scoped to a forthcoming proposal extending the same capability); spec/graph-engine/spec.md (§6 — add two new typed event variants on the observer event union: `EmbeddingEvent` and `EmbeddingFailedEvent`, paralleling `LlmCompletionEvent` + `LlmFailedEvent`); spec/observability/spec.md (§5.5 — OTel mapping for embedding spans using the Stable subset of GenAI semconv attributes plus OA-namespace operation discrimination via span name; §8 — Langfuse mapping using Langfuse's dedicated `Embedding` observation type; §5.5.4 — rename the existing `disable_llm_payload` observer-level privacy flag to `disable_provider_payload` so the flag's scope cleanly covers payload from any provider operation, with cross-references in §8 + graph-engine §6 updated accordingly); plus new conformance fixtures under `spec/retrieval-provider/conformance/` and `spec/observability/conformance/`.
- **Related:** 0006 (llm-provider core — established the per-model-binding + typed-response pattern this proposal mirrors for embedding), 0049 (typed `LlmCompletionEvent` — typed-event pattern on the observer union this extends), 0057 (LlmCompletionEvent field-set extension — request-side / prompt-identity / per-call disambiguator fields this proposal mirrors onto `EmbeddingEvent` from launch rather than via a follow-on cycle), 0058 (LlmFailedEvent typed variant — failure-side typed event paired with the success-side per the success+failure pairing precedent this proposal applies)
- **Supersedes:**

## Summary

Creates a new `retrieval-provider` capability covering non-LLM-completion provider
operations. The capability sits alongside `llm-provider` (proposal 0006) rather than
extending it — embedding (and rerank, in a forthcoming follow-on) have disjoint
per-model-binding semantics from LLM completions: one provider instance binds to one
model identifier per the existing llm-provider §5 contract, and embedding model
identifiers (`text-embedding-3-small`, `voyage-3`, `embed-multilingual-v3.0`, etc.) live
in disjoint namespaces from completion model identifiers (`gpt-4o-mini`,
`claude-3-5-sonnet`, etc.). A single Provider abstraction bundling both surfaces would
contradict the per-model-binding contract or carve a different shape for the same
protocol — both bad.

This proposal lands:

1. The `retrieval-provider` capability scaffold — `spec/retrieval-provider/spec.md` with
   the protocol-naming conventions, error-semantics inheritance from llm-provider §7,
   and the typed-event pairing convention (success + failure variant per protocol from
   day one, per the 0049 → 0058 pairing precedent).
2. The `EmbeddingProvider` protocol — `ready()` + `embed(input: list[str], *, config?) ->
   EmbeddingResponse`, with typed response + usage records mirroring llm-provider §6's
   `Response` shape.
3. Two new typed observer events on the graph-engine §6 observer event union:
   `EmbeddingEvent` (success) and `EmbeddingFailedEvent` (failure). Each carries the
   identity / scoping / request-side field set proposal 0057 established for
   `LlmCompletionEvent`, plus embedding-specific success-side or failure-specific fields.
4. OTel + Langfuse backend mappings for embedding observability — Stable GenAI semconv
   attributes (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`)
   plus OA-namespace `openarmature.embedding.*` attributes; span name
   `openarmature.embedding.complete` discriminates the operation; Langfuse mapping uses
   the dedicated `Embedding` observation type (NOT `Generation` with operation
   metadata — verified against current Langfuse docs at draft time). The upstream
   `gen_ai.operation.name = "embeddings"` attribute is at Development status as of
   draft time and deferred to a follow-on per the stable-only adoption policy.
5. A cross-spec rename of the observer-level privacy flag from `disable_llm_payload` to
   `disable_provider_payload`, folded into this proposal so the embedding-payload
   privacy posture lands on the renamed flag from launch (avoiding a naming-mismatch
   transition window). The semantics broaden to cover payload from any provider call
   (LLM + embedding + rerank when it lands); default-True behavior preserved.

The sibling `RerankProvider` protocol lands in a forthcoming proposal extending the
same capability.

## Motivation

Three forces converge.

**Observability-blind-spot for embedding calls today.** Downstream RAG pipelines hitting
OpenAI-wire-compatible embedding endpoints (Bifrost, Cohere, Voyage AI, Jina AI, etc.)
currently bypass OpenArmature entirely via direct HTTP calls — embedding falls outside
the observability stream (no OTel span, no observer event, no Langfuse `Generation`
observation, no per-invocation cost rollup via the proposal 0048 queryable observer
pattern). The framework's "observable by default" promise has a real hole.

**Per-model-binding is load-bearing.** The llm-provider §5 contract is "one provider
instance, one model identifier." Embedding model identifiers and completion model
identifiers live in disjoint namespaces; a single provider instance bundling both either
contradicts the contract OR carves a different contract shape for the same protocol.
Both options break existing invariants. A separate `EmbeddingProvider` protocol — bound
to its own model identifier per instance — preserves the per-model-binding contract
while opening a path to observable embedding calls.

**Real provider-landscape variance.** OpenAI does completion + embedding (no rerank).
Voyage AI does embedding + rerank (no completion). Anthropic only does completion. Jina
AI mostly does rerank. Cohere does all three. A unified Provider abstraction bundling
all three operations would force every implementation to stub out methods the backend
doesn't serve. Separate protocols let each implementation declare exactly what its
backend supports; downstream pipelines configure one instance per capability they need.

Type signatures stay precise as a fourth-order benefit — `embed()` returns vectors keyed
by input order; `complete()` returns a structured LLM response. A union return type or
generic `query()` method would erase per-capability semantics the type system protects
today.

## Proposed change

### Create `spec/retrieval-provider/spec.md`

A new capability sitting alongside `llm-provider`. The §-structure:

#### §1 Purpose

Frames the retrieval-provider capability as the home for retrieval-primitive provider
operations — embedding (this proposal) and rerank (forthcoming). The capability inherits
llm-provider's per-model-binding contract, error-category enumeration (§7), and typed-
response shape conventions. It does NOT extend llm-provider's `Provider` protocol; the
protocols defined here are siblings, not subtypes.

Retrieval-provider is one of a planned family of `<domain>-provider` capabilities
(`llm-provider`, `retrieval-provider`, plus future siblings as downstream demand
surfaces — e.g., voice-provider for ASR + TTS, multimodal-provider for image
generation + image edit). Each domain capability covers related-shape provider
operations; new domains land as new capabilities rather than as extensions to existing
ones. This keeps per-capability protocol surface narrow and per-domain evolution
independent.

#### §2 Concepts

Defines: `RetrievalProvider` (umbrella term covering both `EmbeddingProvider` and
`RerankProvider`), `EmbeddingResponse` shape, `EmbeddingUsage` record, embedding-specific
runtime config (initially minimal — `dimensions` for callers controlling output size +
the extras pass-through bag).

#### §3 EmbeddingProvider protocol

The `EmbeddingProvider` protocol exposes two async operations:

| Operation | Parameters | Returns |
|---|---|---|
| `ready()` | (none) | void / null |
| `embed(input, *, config?)` | `input`: list of strings; `config`: optional `EmbeddingRuntimeConfig` (keyword-only) | `EmbeddingResponse` record |

Cross-impl contract:

- Per-instance model binding (matches llm-provider §5). Implementations bind one model
  identifier per provider instance via a constructor parameter (or per-language idiomatic
  equivalent).
- `ready()` MUST be idempotent; surfaces `provider_invalid_model` /
  `provider_model_not_loaded` per llm-provider §7 if the bound embedding model is not
  available.
- `embed()` MUST raise one of the llm-provider §7 error categories on failure (the §7
  enumeration is shared cross-capability; embedding-applicable subset documented in §5
  *Error semantics* below).
- Input is always a list of strings — even single-string callers wrap as a one-element
  list. Matches `complete()`'s "always a list" message contract; cleaner type signature
  than overloading the input type.
- The `config` parameter is keyword-only (or per-language idiomatic equivalent that
  prevents positional confusion with `input`).

#### §4 EmbeddingResponse and EmbeddingUsage shapes

An `EmbeddingResponse` record:

| Field | Description |
|---|---|
| `vectors` | List of vectors (each a list of floats); one vector per input string in the order the inputs were supplied. The length of `vectors` MUST equal the length of `input`. |
| `model` | The model identifier the provider returned. MAY be a more specific identifier than the one the provider was bound against. |
| `usage` | An `EmbeddingUsage` record (defined below). |
| `request_id` | The provider-returned request identifier when present; null otherwise. |
| `dimensions` | Int. The output vector dimensionality. MUST equal the length of each inner list in `vectors`; derivable from `vectors[0]` but kept on the response for ergonomics + cross-vendor consistency. |
| `raw` | The parsed provider response, as a language-idiomatic representation of deserialized JSON (Python: `dict[str, Any]`; TypeScript: `Record<string, unknown>`). MUST be populated on every successful return. Parallel to llm-provider §6 `Response.raw`. |

An `EmbeddingUsage` record:

| Field | Description |
|---|---|
| `input_tokens` | Int. Tokens billed for the embedding call. Always reported (no `output_tokens` — vectors aren't tokens). |

Cross-impl invariants:

- Exactly one vector per input string (the length of `vectors` matches the length of
  `input`).
- Vector position is keyed by input order; implementations MUST NOT permute.
- All vectors in a single response have the same dimensionality. Implementations MUST
  verify this on the response and raise `provider_invalid_response` per llm-provider §7
  if violated.
- The `dimensions` field on the response MUST equal the dimensionality of each inner
  vector — cross-check invariant for adapters.

#### §5 Error semantics

Inherits the llm-provider §7 error-category enumeration. The embedding-applicable subset
is the §7 categories minus the LLM-completion-specific ones:

- `provider_authentication`, `provider_unavailable`, `provider_invalid_model`,
  `provider_model_not_loaded`, `provider_rate_limit`, `provider_invalid_response`,
  `provider_invalid_request` — all apply
- `provider_unsupported_content_block` — does NOT apply (embedding takes strings, not
  content blocks)
- `structured_output_invalid` — does NOT apply (embedding has no `response_schema`)

#### §6 Determinism

Embedding model determinism guarantees vary by provider; the spec MUST NOT assume
bit-identical vectors for equivalent inputs. Embedding-aware caches keyed on input strings
(e.g., the proposal 0047 prefix-cache analog) MAY apply per the provider's documented
determinism guarantees but are NOT a spec contract.

#### §7 Cross-spec touchpoints

- graph-engine §6 — typed observer events `EmbeddingEvent` + `EmbeddingFailedEvent`
- observability §5.5 (OTel) + §8 (Langfuse) — backend mappings
- llm-provider §7 — error-category enumeration (inherited)
- pipeline-utilities §6 (middleware) — `EmbeddingProvider` calls are eligible for retry
  middleware identically to `complete()` calls

#### §8 Out of scope

- Multi-modal embedding (image / audio embeddings). Text-only in v1.
- Per-vendor wire-format mappings. Follow-on proposals add OpenAI / Cohere / Voyage / etc.
  mappings analogous to llm-provider §8.1 / §8.2 / §8.3.
- Per-SDK implementation details (httpx batching strategies, retry timing).
- Caller-supplied determinism / seeding (embedding models rarely expose seeds; not v1).
- Cross-call observability correlation (e.g., "this rerank call used vectors from that
  embedding call"). Each call is independent at the protocol layer; any correlation lives
  in node-body code, not in the protocol contract.

### Extend graph-engine §6 with `EmbeddingEvent` + `EmbeddingFailedEvent`

Two new typed event variants on the observer event union, paired from day one per the
0049 → 0058 success+failure pairing precedent. Both follow the type-discrimination
pattern (`isinstance(event, EmbeddingEvent)` / `isinstance(event, EmbeddingFailedEvent)`)
established by 0049 for the LLM-side variants.

#### `EmbeddingEvent` (success)

Mirrors the shape of `LlmCompletionEvent`'s identity / scoping / request-side field
set per the 0057-extended baseline, with capability-specific substitutions
(`input_strings` in place of `input_messages`). Embedding-specific success-side fields
replace the LLM-completion-specific ones:

| Field | Type | Description |
|---|---|---|
| `invocation_id` | string | The outer invocation's identifier, per observability §5.1. |
| `correlation_id` | string \| null | Cross-backend correlation ID, per observability §3.1. |
| `node_name` | string | The user-defined node that issued the call. |
| `namespace` | sequence of strings | The calling node's namespace, per the *Node event shape* above. |
| `attempt_index` | int | The retry-attempt index (0 on the first attempt). |
| `fan_out_index` | int \| null | The fan-out instance index when the calling node ran inside a fan-out instance (per pipeline-utilities §9). Null otherwise. |
| `branch_name` | string \| null | The parallel-branches branch name when the calling node ran inside a parallel-branches branch (per pipeline-utilities §11). Null otherwise. |
| `provider` | string | The embedding provider identifier (matches `gen_ai.system` per observability §5.5.3). |
| `model` | string | The model identifier the request was made against. |
| `response_model` | string \| null | The model identifier the provider returned in the response (matches `gen_ai.response.model`). May be more specific than requested; null when the provider doesn't return a response model. |
| `response_id` | string \| null | The provider-returned response identifier, when present. |
| `usage` | record \| null | `EmbeddingUsage` record per retrieval-provider §4. May be null when the provider does not report usage. |
| `latency_ms` | float \| null | Wall-clock latency of the embedding call measured at the adapter boundary, in milliseconds. May be null when latency is not measured. Implementations MAY use a provider-reported latency value when the provider surfaces one, documenting which source is in use. |
| `finish_reason` | n/a | Embedding has no completion semantics; field omitted from this variant. |
| `caller_invocation_metadata` | mapping \| null | OPTIONAL field; same opt-in semantics as on `LlmCompletionEvent`. |
| `input_strings` | list of string | The input strings the embedding call was made with, in the typed-event-native form. Populated unconditionally on every typed event; observer-side privacy gating applies at the rendering boundary per the privacy paragraph below. |
| `request_params` | mapping | Embedding-specific `EmbeddingRuntimeConfig` fields the caller supplied (`dimensions`, etc.). Absence-is-meaningful semantics per the equivalent field on `LlmCompletionEvent`. Empty mapping when no parameters were supplied. |
| `request_extras` | mapping | The `EmbeddingRuntimeConfig` extras pass-through bag — vendor-specific knobs. Same shape and privacy posture as on `LlmCompletionEvent`. |
| `active_prompt` | record \| null | A snapshot of the active `Prompt` identity at embedding-call time (RAG pipelines often render a prompt template before embedding for chat-shaped search). Same field set and nullability as on `LlmCompletionEvent`. |
| `active_prompt_group` | record \| null | Snapshot of the active `PromptGroup` identity. Same shape as on `LlmCompletionEvent`. |
| `call_id` | string | A per-call disambiguator minted by the implementation. **Always present** (never null); freshly minted per `embed()` call. |
| `input_count` | int | The number of input strings the call was made with (equals `len(input_strings)`). Derivable but kept for ergonomics + cross-vendor consistency. |
| `dimensions` | int \| null | The dimensionality of the returned vectors (equals the inner-vector length from the response). May be null when the response does not surface a determinate dimensionality. |

#### `EmbeddingFailedEvent` (failure)

Same shape as `LlmFailedEvent` (proposal 0058) — mirrors the identity / scoping /
request-side field set from `EmbeddingEvent`, with embedding-specific success-side
fields (`response_id`, `response_model`, `usage`, `dimensions`, `input_count`) absent
(no vectors were returned), and adds three failure-specific fields:

| Field | Type | Description |
|---|---|---|
| `invocation_id` | string | The outer invocation's identifier, per observability §5.1. |
| `correlation_id` | string \| null | Cross-backend correlation ID, per observability §3.1. |
| `node_name` | string | The user-defined node that issued the call. |
| `namespace` | sequence of strings | The calling node's namespace, per the *Node event shape* above. |
| `attempt_index` | int | The retry-attempt index (0 on the first attempt). |
| `fan_out_index` | int \| null | The fan-out instance index when the calling node ran inside a fan-out instance (per pipeline-utilities §9). Null otherwise. |
| `branch_name` | string \| null | The parallel-branches branch name when the calling node ran inside a parallel-branches branch (per pipeline-utilities §11). Null otherwise. |
| `provider` | string | The embedding provider identifier. |
| `model` | string | The model identifier the request was made against. |
| `latency_ms` | float \| null | Wall-clock latency from `embed()` entry to the point the failure was raised, in milliseconds. May be null when latency is not measured. |
| `caller_invocation_metadata` | mapping \| null | OPTIONAL field; same opt-in semantics as on `EmbeddingEvent`. |
| `input_strings` | list of string | The input strings the embedding call was made with. Populated unconditionally on every typed event; same observer-side privacy-gating posture as on `EmbeddingEvent`. |
| `request_params` | mapping | Embedding-specific config fields the caller supplied. Same shape as on `EmbeddingEvent`. |
| `request_extras` | mapping | The `EmbeddingRuntimeConfig` extras pass-through bag. Same shape and privacy posture as on `EmbeddingEvent`. |
| `active_prompt` | record \| null | Snapshot of the active `Prompt` identity at embedding-call time. Same shape as on `EmbeddingEvent`. |
| `active_prompt_group` | record \| null | Snapshot of the active `PromptGroup` identity. Same shape as on `EmbeddingEvent`. |
| `call_id` | string | A per-call disambiguator minted by the implementation. **Always present**; freshly minted per `embed()` call. A failed call gets its own `call_id`, distinct from any retry-attempt sibling. |
| `error_category` | string | One of the llm-provider §7 normative categories applicable to embedding (per retrieval-provider §5 above). Always present. |
| `error_type` | string \| null | OPTIONAL impl-level / vendor-specific error type or code. Two acceptable styles (vendor error code, upstream exception class name). Null when no impl-side type is available. |
| `error_message` | string | Human-readable message from the raised exception. Always present (empty string when the exception carried no message). |

#### Mutual exclusion + exception-flow + dispatch timing

Same rules as 0058's `LlmCompletionEvent` / `LlmFailedEvent` pair:

- `EmbeddingEvent` and `EmbeddingFailedEvent` are mutually exclusive on a given `embed()`
  call. Implementations MUST NOT emit both for the same call.
- The §7 category exception still raises out of `embed()` per llm-provider §7 — whether
  raised by the provider or by the implementation's pre-send validation layer. The typed
  event is dispatched alongside the exception, not in place of it.
- Both events MUST be dispatched on the observer delivery queue at the point of `embed()`
  completion or failure (after success / after exception is raised; before the call
  returns or re-raises to the caller). Delivery semantics follow graph-engine §6 — strict-
  serial across the invocation, async-delivered.

#### Privacy posture

`input_strings` and `request_extras` carry potentially sensitive payload data
(RAG-pipeline indexing of user-supplied text). The privacy posture is identical to
`LlmCompletionEvent`'s — observer-side gating at the rendering boundary per observability
§5.5.4 (implementations populate the fields unconditionally; observers honor
`disable_provider_payload`). The `disable_provider_payload` flag's semantics extend to cover all
LLM-adjacent provider operations (LLM completion + embedding + rerank when it ships)
rather than proliferating per-operation flags.

### Rename observability §5.5.4 `disable_llm_payload` → `disable_provider_payload`

The observer-level flag defined at observability §5.5.4 currently gates LLM payload
data — `input.messages`, `output.content`, `request.extras` per §5.5.1 — from being
populated on OTel spans and Langfuse `Generation` observations. With the addition of
embedding (this proposal) and forthcoming rerank as provider operations whose payload
needs the same gating, the flag's `_llm_` infix is too narrow.

Rename the flag from `disable_llm_payload` to `disable_provider_payload`. Semantics
broaden to cover payload data from any provider call (LLM completion + embedding +
rerank when it lands), under a single observer-level flag with default `True`
(suppressed by default) — same default-conservative posture as today. No semantic
change beyond the broadened scope; existing LLM-payload gating behavior is preserved
unchanged for `LlmCompletionEvent` + `LlmFailedEvent` (proposals 0049 / 0057 / 0058).

Spec text edits at Accept time:

- observability §5.5.4 renames the flag definition + extends the framing to cover
  provider-payload data across LLM + embedding + rerank uniformly
- observability §8 / §8.4 references update to the new name
- graph-engine §6's `LlmCompletionEvent` + `LlmFailedEvent` privacy paragraphs update
  references
- Existing fixtures using the flag rename in their YAML (the OTel `disable_llm_payload`
  toggle is exercised by fixtures 013 + 018; both swap the key)

Pre-1.0 SemVer convention permits the hard-swap rename in a MINOR bump; same precedent
as proposal 0057's `request_id` → `response_id` field rename. The CHANGELOG entry calls
out the rename in the **Changed** section so any downstream observer config with
`disable_llm_payload=True` has operator-awareness for the one-key update.

### Extend observability §5.5 (OTel) with embedding mapping

A new §5.5.X *Embedding provider attributes* sub-subsection paralleling the existing
§5.5 *LLM provider attributes* block.

**Span name** — `openarmature.embedding.complete` (parallel to the existing
`openarmature.llm.complete` span name for LLM completions). Span name discriminates the
operation type without requiring an explicit operation-name attribute. Parent is the
calling node's span.

**Stable GenAI semconv attributes** (mapped where they apply directly):

- `gen_ai.system` ← `EmbeddingProvider`'s configured provider identifier (e.g.,
  `"openai"`, `"voyageai"`, `"cohere"`)
- `gen_ai.request.model` ← bound embedding model identifier
- `gen_ai.response.model` ← `EmbeddingResponse.model` (provider-echoed)
- `gen_ai.response.id` ← `EmbeddingResponse.request_id` (when present)
- `gen_ai.usage.input_tokens` ← `EmbeddingResponse.usage.input_tokens`

**OA-namespace attributes**:

- `openarmature.embedding.input_count` — int — number of input strings
- `openarmature.embedding.dimensions` — int — output vector dimensionality
- `openarmature.embedding.input.strings` — JSON-encoded list of input strings (subject
  to `disable_provider_payload`, parallel to §5.5.1)
- `openarmature.embedding.request.extras` — JSON-encoded extras mapping (subject to
  `disable_provider_payload`)

**Stable-only upstream adoption — operation-name attribute deferred.** The upstream OTel
GenAI semconv `gen_ai.operation.name` attribute (with `"embeddings"` as a documented
well-known value) is at **Development** status as of OTel semconv (verified at draft
time); per the `Stable-only upstream adoption` policy in `GOVERNANCE.md` (and tracked
in `docs/compatibility.md`), OA does NOT normatively adopt this attribute in v1.
Operation discrimination is via the span name + provider; a follow-on proposal MAY add
`gen_ai.operation.name = "embeddings"` to the attribute surface when the upstream
attribute reaches **Stable** status, per the §5.5.3.1 / 0047 mirror pattern.

The `disable_llm_spans` / `disable_provider_payload` / `disable_genai_semconv` flags apply
analogously to embedding spans.

A new §5.5.X *Typed embedding events* sub-subsection frames the
`EmbeddingEvent` + `EmbeddingFailedEvent` typed-event surface as the structured form of
the embedding attribute surface, paralleling §5.5.7 for LLM completion events.

### Extend observability §8 (Langfuse) with embedding mapping

A new §8.X *Embedding observation mapping* sub-subsection. Embedding calls map onto
Langfuse's dedicated `Embedding` observation type (created via the SDK's
`asType: "embedding"` parameter or per-language idiomatic equivalent), NOT `Generation`.

Field mappings:

- `embedding.model` ← `EmbeddingResponse.model`
- `embedding.input` ← `input_strings` (privacy-gated per `disable_provider_payload` —
  see *Privacy posture for embedding observations* below)
- `embedding.output` ← `EmbeddingResponse.vectors` (the actual embedding vectors;
  privacy-gated per `disable_provider_payload`)
- `embedding.usageDetails.input` ← `EmbeddingResponse.usage.input_tokens`
- `embedding.metadata.openarmature_input_count`,
  `embedding.metadata.openarmature_dimensions`,
  `embedding.metadata.openarmature_request_id` (when present)

Trace-level cost rollup aggregates across LLM `Generation` + `Embedding` observations
uniformly — Langfuse's cost-tracking machinery understands the `Embedding` type's
`usageDetails` field directly. No metadata discriminator is needed; the observation type
itself discriminates.

**Privacy posture for embedding observations.** Both `input` strings and `output`
vectors are payload-bearing data on the same footing — both gated by
`disable_provider_payload` (default `True` per observability §5.5.4 — see *Rename* below
for the cross-spec flag rename folded into this proposal). When the flag is `True`, the
`Embedding` observation populates `model` + `usageDetails` + identity metadata only;
both `input` and `output` are NOT populated. When `False`, both fields populate fully.

Vectors are classified as payload-bearing because embedding-inversion research (e.g.,
the vec2text line of work, Morris et al., 2023) demonstrates that vectors MAY leak
source-text information given the embedding model. The threat model for vectors is
equivalent to the threat model for raw text from the spec's perspective; gating applies
uniformly. RAG applications in particular have a corpus-leakage concern — the (text,
vector) pairs accumulated in traces would let an attacker reconstruct the embedding
index and query it offline. Default-suppression is the conservative posture.

A future observability proposal MAY introduce a tiered preview mode (e.g., truncated
`input` strings + first-N-dimensions vectors) for users wanting partial visibility
without full payload exposure. Out of scope for this proposal.

## Conformance test impact

### New fixtures under `spec/retrieval-provider/conformance/`

A new directory for the retrieval-provider capability's own protocol-level fixtures:

1. **`001-embed-positive-control`** — Bound `EmbeddingProvider` with a mocked provider
   that returns 3 vectors for 3 input strings. Asserts response shape: the length of
   `vectors` matches the length of `input`, all inner vectors have the same length, the
   `dimensions` field matches the inner-vector length, `usage.input_tokens` populated,
   `request_id` populated.
2. **`002-embed-model-binding-error`** — `EmbeddingProvider` instantiated with an
   unknown model id; `ready()` raises `provider_invalid_model`. Verifies model-binding
   contract per retrieval-provider §3 / llm-provider §7.
3. **`003-embed-malformed-response-mismatched-vector-count`** — Provider returns 2
   vectors for 3 input strings; `embed()` raises `provider_invalid_response` per §5.
4. **`004-embed-malformed-response-inconsistent-dimensions`** — Provider returns 3
   vectors with inconsistent inner-list lengths; `embed()` raises
   `provider_invalid_response`.
5. **`005-embed-input-order-preserved`** — Input order MUST be preserved in output
   vector order. Mocked provider returns identifiable vectors; assert output indexes
   match input indexes.

### New fixtures under `spec/observability/conformance/`

Parallel to the 050-073 LLM-event fixtures, covering both `EmbeddingEvent` and
`EmbeddingFailedEvent`. Final fixture numbers assigned at acceptance; the rough block
is 074-085:

- **`07X-embedding-event-dispatch`** — Successful `embed()` call dispatches
  `EmbeddingEvent` with the full field set populated. Mirrors 050 for LLM.
- **`07X-embedding-failure-event-dispatch-on-provider-unavailable`** — Failed `embed()`
  call dispatches `EmbeddingFailedEvent`; exception still raises. Mirrors 069.
- **`07X-embedding-event-mutual-exclusion`** — Successful call emits exactly one
  `EmbeddingEvent` and zero `EmbeddingFailedEvent`; failed call emits exactly one
  `EmbeddingFailedEvent` and zero `EmbeddingEvent`. Mirrors 072.
- **`07X-embedding-event-call-id-distinct`** — Multiple `embed()` calls in an invocation
  emit `EmbeddingEvent`s with distinct `call_id` values. Mirrors 067.
- **`07X-embedding-event-input-strings-populated`** — `input_strings` field carries the
  input list verbatim. Mirrors 060.
- **`07X-embedding-event-request-params-populated`** — `request_params` carries
  `dimensions` when supplied; absence-is-meaningful for other params. Mirrors 062.
- **`07X-embedding-event-input-count-and-dimensions-populated`** — Convenience fields
  match the input list length and the inner-vector length from the response.
- **`07X-embedding-event-active-prompt-populated`** — Embedding call inside a prompt-
  context binding carries `active_prompt` snapshot. Mirrors 064.
- **`07X-otel-embedding-span-attributes`** — OTel span emitted with span name
  `openarmature.embedding.complete` and the Stable GenAI semconv attribute subset
  (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.response.model`,
  `gen_ai.response.id`, `gen_ai.usage.input_tokens`) plus the OA-namespace embedding
  attributes. Asserts the upstream `gen_ai.operation.name` attribute is NOT emitted in
  v1 per the stable-only deferral.
- **`07X-langfuse-embedding-observation`** — Langfuse dedicated `Embedding` observation
  (created via `asType: "embedding"` per Langfuse SDK convention), with `model` +
  `usageDetails.input` + identity metadata populated. Two cases: (1) with
  `disable_provider_payload=True` (default) — `input` and `output` NOT populated;
  (2) with `disable_provider_payload=False` — `input` carries the strings list,
  `output` carries the full vectors. Asserts the observation type is `Embedding` (not
  `Generation`).

## Versioning

**MINOR bump** (pre-1.0). On acceptance:

- New `retrieval-provider` capability — purely additive; no existing capability touched
- Two new typed event variants on the graph-engine §6 observer event union —
  `EmbeddingEvent`, `EmbeddingFailedEvent`
- New §5.5.X / §8.X subsections in observability spec — additive
- One breaking-name rename: observer-level privacy flag `disable_llm_payload` →
  `disable_provider_payload` (per the *Rename observability §5.5.4* section above).
  Pre-1.0 SemVer convention permits the rename in a MINOR bump; the CHANGELOG entry
  carries the rename in **Changed** for downstream operator-awareness.
- ~5 fixtures under `spec/retrieval-provider/conformance/` (new directory) + ~10
  fixtures under `spec/observability/conformance/` + 2 existing observability fixtures
  rename one config key (the `disable_llm_payload` flag in fixtures 013 + 018)

Observers consuming only `LlmCompletionEvent` / `LlmFailedEvent` continue to work
unchanged at the typed-event surface; one observer-config key change is required to
adopt v0.54.0 (`disable_llm_payload` → `disable_provider_payload`).

## Alternatives considered

1. **Extend `llm-provider` with `embed()` on the same `Provider` protocol.** Reject —
   contradicts per-model-binding (a `Provider` instance can't simultaneously be bound to
   `gpt-4o-mini` AND `text-embedding-3-small`; the existing llm-provider §5 contract is
   one instance, one model). The single-protocol-with-overloaded-binding shape would
   break invariants other capabilities depend on (cross-cutting `gen_ai.request.model`
   span attribute; per-instance retry config; per-model conformance fixtures).

2. **Single unified `Provider` with `embed()` + `complete()` + `rerank()` methods.**
   Reject — the real provider landscape is fragmented (OpenAI does complete+embed,
   Voyage does embed+rerank, Anthropic only complete, Cohere all three). A unified
   protocol forces every implementation to stub out methods its backend doesn't serve.
   Separate protocols let each implementation declare exactly what its backend supports.

3. **Name the success event `EmbeddingCompletionEvent` for cross-family symmetry with
   `LlmCompletionEvent`.** Reject — "Completion" is the LLM term of art (one model =
   many tokens completing a response); embedding doesn't "complete" semantically. The
   shorter `EmbeddingEvent` reads more accurately at the cost of less mechanical
   cross-family symmetry. Same call applies to the forthcoming rerank variant
   (`RerankEvent`, not `RerankCompletionEvent`).

4. **Ship the success-side event variant only; defer the failure-side typed variant.**
   Reject — the 0049 → 0058 split was a real cost. Observers had a typed-event surface
   for the success path and a sentinel-namespace `NodeEvent` for the failure path,
   defeating the type-discrimination contract on the failure side and requiring two
   release cycles to complete the typed-event coverage. Shipping both variants together
   from launch avoids that split.

5. **Ship with a minimal field set; extend later via a follow-on proposal.** Reject —
   the 0049 → 0057 extension was a similar cost. The typed event landed minimally at
   v0.41.0, then needed re-extension to add request-side / prompt-identity / per-call
   disambiguator fields at v0.51.0. Shipping the full 0057-extended baseline from launch
   skips that beat.

6. **Two separate capabilities — `embedding-provider` + `rerank-provider`.** Reject —
   over-fragmentation. Embedding and rerank are both retrieval primitives; a single
   `retrieval-provider` capability with two protocol surfaces is the cleaner home. The
   sibling protocol-shape framing parallels how `harness` is one capability with
   per-harness-type sub-specs (chat, FastAPI, etc.).

7. **Define `disable_embedding_payload` as a separate observer-side privacy flag;
   keep `disable_llm_payload` for LLM completion.** Reject — privacy-flag
   proliferation. Each new capability would get its own per-operation flag, ratcheting
   the observer-config surface as the spec grows. A single renamed
   `disable_provider_payload` covers all provider-payload data under one mental model.

8. **Ship 0059 using the existing `disable_llm_payload` flag name unchanged; carry the
   naming mismatch.** Reject — `disable_llm_payload=True` covering non-LLM embedding
   payload reads as an outright bug to any reader. Renaming now (pre-1.0, folded into
   this proposal) is cheap; deferring locks in the mismatch through the impl cycle
   absorbing this work and accumulates downstream config-key technical debt.

9. **Map embeddings onto Langfuse's `Generation` observation type with a
   `metadata.operation = "embedding"` discriminator.** Reject — verified against
   Langfuse docs at draft time that Langfuse exposes a dedicated `Embedding`
   observation type (10 observation types currently: Event, Span, Generation, Agent,
   Tool, Chain, Retriever, Evaluator, Embedding, Guardrail). The dedicated type
   carries the semantic accuracy + cost-rollup integration directly; the
   `Generation`-with-discriminator framing was an outdated assumption from an earlier
   Langfuse data model.

## Open questions

None at draft time. All design choices are settled in the proposal text above:

- **Capability home** — new `spec/retrieval-provider/` capability (per the user-aligned
  direction; not extending llm-provider, not separate-capability-per-protocol).
- **Protocol shape** — `EmbeddingProvider` is a sibling protocol to `Provider`, with its
  own `ready()` + `embed()` interface and per-model binding.
- **Event variant naming** — `EmbeddingEvent` + `EmbeddingFailedEvent`; "Completion"
  suffix dropped for accuracy over cross-family symmetry.
- **Success+failure pairing** — both event variants ship in this proposal from day one;
  no follow-on split.
- **Field set scope** — request-side / prompt-identity / per-call disambiguator fields
  included from launch per the 0057 precedent; no follow-on extension cycle planned.
- **Privacy posture** — `disable_provider_payload` (renamed from `disable_llm_payload`;
  see *Rename observability §5.5.4* in Proposed change) semantics cover embedding
  payload including vectors. Vectors are payload-bearing because embedding-inversion
  research (vec2text and related lines of work) demonstrates that vectors MAY leak
  source-text information given the embedding model — the threat model is equivalent
  to raw text from the spec's perspective; gating applies uniformly. A future
  observability proposal MAY introduce a tiered preview mode (truncated strings +
  first-N-dimensions vectors) for partial-visibility use cases; out of scope here.
- **Langfuse observation type** — dedicated `Embedding` type (created via
  `asType: "embedding"`), NOT `Generation` with operation metadata. Verified against
  current Langfuse docs at draft time — Langfuse exposes 10 observation types
  including a first-class `Embedding` type with `model` + `usageDetails` + `input` +
  `output` fields tailored to embedding calls. The dedicated type carries both
  semantic accuracy and the cost-rollup integration cleanly.
- **`disable_llm_payload` rename** — folded into this proposal (Option B from the
  drafting discussion). Pre-1.0 SemVer convention permits the hard-swap rename in a
  MINOR bump; same precedent as proposal 0057's `request_id` → `response_id` rename.
  The new name avoids a naming-mismatch transition window where the embedding-payload
  flag would be called `disable_llm_payload` despite covering non-LLM payload.
- **Error categories** — inherited from llm-provider §7; embedding-applicable subset
  documented in retrieval-provider §5.
- **Sequencing** — rerank protocol lands in a follow-on proposal extending the same
  capability; this proposal scopes to the capability scaffold + embedding only.
- **Stable-only upstream adoption for `gen_ai.operation.name`** — the upstream OTel
  GenAI semconv `gen_ai.operation.name` attribute (with `"embeddings"` as a documented
  well-known value) is at **Development** status as of draft time (verified against
  the OTel GenAI spans semantic conventions). Per the `Stable-only upstream adoption`
  policy in `GOVERNANCE.md`, OA does NOT normatively adopt this attribute in v1.
  Operation discrimination is via span name + provider; the attribute MAY be added in
  a follow-on when upstream reaches Stable. Same mirror pattern as proposal 0047's
  cache-attribute deferral.

## Out of scope

- **Rerank protocol** — lands in a forthcoming proposal extending the same
  `retrieval-provider` capability with `RerankProvider` + paired `RerankEvent` /
  `RerankFailedEvent`.
- **Multi-modal embedding** (image embeddings, audio embeddings). Text-only in v1; a
  follow-on proposal can scope multi-modal if downstream demand surfaces.
- **Per-vendor wire-format mappings.** Follow-on proposals add concrete vendor mappings
  (OpenAI, Cohere, Voyage, Jina) analogous to llm-provider §8.1 / §8.2 / §8.3.
- **Per-SDK implementation details** — httpx batching strategies, embedding-layer retry
  timing, SDK-specific error mapping. Provider-internal choices.
- **Caller-supplied determinism / seeding.** Embedding models rarely expose seeds; not
  v1. A follow-on can scope if demand surfaces.
- **Cross-call observability correlation** (e.g., "this rerank call used vectors from
  that embedding call"). Each call is independent at the protocol layer; any
  cross-call correlation lives in node-body code.
- **Embedding result caching at the framework level.** Caching is an application
  concern; the framework MAY ship cache middleware in a follow-on proposal, but caching
  is not a protocol-layer contract.
- **A typed-event surface for streaming embeddings.** Some providers stream embeddings
  for very long inputs; not v1. A follow-on can add streaming-event variants per the
  shape forthcoming streaming proposals establish for LLM completions.
