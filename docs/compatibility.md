# External-dependency compatibility

**Last refreshed:** 2026-08-27

OpenArmature normatively references several external specifications and APIs.
This page is the **operational tracking artifact** for those references:
pinned versions, last-verified dates, and per-dependency adoption notes.

Everything above *Implementation support* records what the **specification
text** is written against, which is one answer per dependency and the same
answer whichever implementation you use.
[Implementation support](#implementation-support) records the separate
per-implementation view: which version range an implementation publishes to
its consumers, which version it has actually verified, and how much
unsupported private surface it reaches into. Those legitimately differ from
the spec-side row and from each other, so they are tracked apart rather than
reconciled into a single number.

The **normative policy** governing how OA adopts upstream changes lives in
[Governance — External-dependency adoption](governance.md). In brief:

- OA normatively adopts upstream attribute names / wire shapes **only when
  the upstream marks them Stable** (or equivalent maturity marker per
  upstream governance).
- Pre-stable upstream attributes (Development, Experimental, Beta, etc.)
  are mirrored to the `openarmature.*` namespace until they stabilize.
- OA implementations MUST emit the OA-namespace names when this spec
  mandates OA-namespace mirroring — they MUST NOT jump ahead to
  upstream pre-stable attribute names.

**Stability vocabulary.** Each upstream uses its own maturity vocabulary —
OA tracks whatever marker the upstream itself uses (OpenTelemetry semconv
uses `Stable` / `Development` / `Experimental` / `Deprecated`; semver SDKs
use pre-release tags vs. stable releases; IETF uses publication track —
Standards Track, Best Current Practice, Informational, etc.). The
**Upstream status** column below records the marker as the upstream
publishes it.

## Compatibility matrix

| Dependency | OA-tracked version / scope | Upstream status | Last verified | Notes |
|---|---|---|---|---|
| [OpenTelemetry semantic conventions](https://github.com/open-telemetry/semantic-conventions) | v1.41.1 (core); GenAI in [semantic-conventions-genai](https://github.com/open-telemetry/semantic-conventions-genai) | Mixed (core Stable; GenAI all Development) | 2026-06-17 | Core semconv (`otel.*`, `error.type`) adopted directly when Stable. The GenAI `gen_ai.*` conventions moved to a dedicated repo where the whole surface is Development (verified 2026-06-17); OA adopts the recognized **core** names directly per the GenAI de-facto-standard carve-out (governance), mirrors peripheral ones (`gen_ai.usage.cache_read.*`, `gen_ai.operation.name`) to `openarmature.*`, and **retains** `gen_ai.system` (upstream-removed → `gen_ai.provider.name`) per the post-adoption retention rule. See detail below. |
| [OpenTelemetry trace + span core spec](https://opentelemetry.io/docs/specs/otel/trace/) | Tracking v1.41.x line | Stable | 2026-05-31 | Span / attribute / status semantics referenced in observability §3–§7. |
| [OpenTelemetry Logs data model](https://opentelemetry.io/docs/specs/otel/logs/data-model/) | `LogRecord` shape; the top-level `EventName` field | Stable | 2026-08-27 | Observability §7 *Diagnostic event names* carries openarmature's diagnostic identifiers on `LogRecord.EventName`, which the data model defines as "Name that identifies the class / type of the Event". Verified 2026-08-27 against the published data model: the field exists as a top-level `LogRecord` field with that definition, and the **document** carries Stable status. The field is not separately stability-marked within the document, so adoption rests on the document's status. Distinct from the Event **semantic conventions**, which prescribe particular event names and remain Development; openarmature names its own diagnostics in the `openarmature.` namespace and takes no name from them. |
| [OpenAI Chat Completions API](https://platform.openai.com/docs/api-reference/chat) | URL-path `v1`; ChatCompletions shape | Stable (continuously updated) | 2026-05-31 | Wire shape per llm-provider §8.1. `usage.prompt_tokens_details.cached_tokens` confirmed present for prompt caching (≥1024-token threshold). |
| [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses) | URL-path `v1`; Responses shape | Stable (continuously updated) | 2026-05-31 | Newer companion API shape; `usage.input_tokens_details.cached_tokens` rather than `prompt_tokens_details`. Not currently referenced by llm-provider §8.X. |
| [Anthropic Messages API](https://docs.anthropic.com/en/api/messages) | Header `anthropic-version: 2023-06-01` | Stable (date-versioned) | 2026-05-31 | Wire shape per llm-provider §8.2. **No implicit caching** — `cache_read_input_tokens` / `cache_creation_input_tokens` fire only under explicit `cache_control` annotations. |
| [Google Gemini API](https://ai.google.dev/api) | URL-path `v1`; model `gemini-2.5+` for implicit caching | Stable (URL-path versioned) | 2026-05-31 | Wire shape per llm-provider §8.3. Implicit caching default-on for Gemini 2.5+ models; `cachedContentTokenCount` populated in `usageMetadata` for both implicit and explicit cache hits. |
| [OpenAI streaming + reasoning-delta extension](https://platform.openai.com/docs/api-reference/chat/streaming) | Chat Completions SSE; `stream_options.include_usage`; vLLM / DeepSeek reasoning-delta ext | Stable (OpenAI SSE); reasoning-delta is a non-standard server extension | 2026-06-20 | Wire shape per llm-provider §8.1.6. OpenAI streams content / tool-call deltas as SSE `data:` chunks, `finish_reason` on the last content chunk, a final empty-`choices` chunk carrying `usage` (with `stream_options.include_usage`), then `[DONE]`. Reasoning streaming is a non-standard OpenAI-compatible **extension** with divergent field names — `choices[].delta.reasoning_content` (DeepSeek / older vLLM) and `choices[].delta.reasoning` (current vLLM); base OpenAI does not stream raw reasoning. |
| [HuggingFace Text Embeddings Inference (TEI)](https://github.com/huggingface/text-embeddings-inference) | self-hosted; `/embed` + `/rerank`; `max-client-batch-size` default 32 | OSS (OpenAPI, continuously updated) | 2026-06-22 | Wire shape per retrieval-provider §8.1. Verified against the TEI OpenAPI: `/rerank` `{query, texts, truncate (default false), return_text (default false), raw_scores, truncation_direction}` → `[{index, score, text?}]` (no guaranteed sort order); `/embed` `{inputs, normalize, dimensions, truncate, prompt_name}`; `prompt_name` realizes the `input_type` knob server-side; mandatory client-side chunk-and-stitch at `max-client-batch-size` (default 32). |
| [Jina AI Search Foundation API](https://jina.ai/) | hosted; `/v1/rerank` + `/v1/embeddings` | Stable (continuously updated) | 2026-07-12 | Wire shape per retrieval-provider §8.2. Verified against the Jina OpenAPI: `/v1/rerank` `{model, query, documents, top_n, return_documents (default `true`), truncation}` → `{results: [{index, relevance_score, document?}], usage: {total_tokens}}`; `/v1/embeddings` `{model, input, task, dimensions, truncate}` → `{data, usage}`. **`task` is MODEL-DEPENDENT** (re-verified against the Jina OpenAPI 2026-07-12): `jina-embeddings-v3` ∈ `retrieval.query` / `retrieval.passage` / `text-matching` / `classification` / `separation` (**no** `clustering`); `jina-embeddings-v4` ∈ `text-matching` / `retrieval.query` / `retrieval.passage` / `code.query` / `code.passage` (**neither** `classification` nor `clustering`); `jina-embeddings-v5` ∈ `retrieval.query` / `retrieval.passage` / `text-matching` / `clustering` / `classification`. This per-model divergence is why §8.2 keeps a closed `input_type` set (a provider is bound to a model identifier, with no capability registry to consult) while §8.4 Cohere widens — see proposal 0099. `return_documents` defaults `true` (vs OA's `False` — the mapping sends it explicitly); `input_type` realized via `task`. Jina enforces **no** per-call input-count cap (server-side token batching) — the §8 *Batch chunking* rule's no-cap branch applies (verified 2026-06-30). |
| [OpenAI Embeddings API](https://platform.openai.com/docs/api-reference/embeddings) | URL-path `v1`; `/v1/embeddings` shape | Stable (continuously updated) | 2026-07-24 | Wire shape per retrieval-provider §8.3 (OpenAI-compatible). Verified against the OpenAI OpenAPI: `/v1/embeddings` `{model, input, dimensions, encoding_format (`float`/`base64`), user}` → `{object: "list", data: [{object: "embedding", index, embedding}], model, usage: {prompt_tokens, total_tokens}}`; **no** query/document `input_type` (symmetric — `input_type` not realized on the wire). `base_url`-configurable, covering the OpenAI-compatible ecosystem (vLLM, LocalAI, Together, …). Per-call cap **2048 inputs** → the §8 *Batch chunking* rule (count-based); the separate per-request summed-token ceiling is provider-enforced fail-loud (`provider_invalid_request`, §8.3), **not** a chunking trigger (verified 2026-06-30). `encoding_format: "base64"` returns each `data[].embedding` as a base64-encoded little-endian IEEE-754 float32 array; §8.3 decodes it to the float vector (proposal 0106, verified 2026-07-24). |
| [Cohere v2 API (rerank + embed)](https://docs.cohere.com/reference/rerank) | hosted; `/v2/rerank` + `/v2/embed` shapes | Stable (continuously updated) | 2026-07-12 | Wire shape per retrieval-provider §8.4. Verified against the Cohere v2 API reference. **`/v2/rerank`:** `{model, query, documents (strings only), top_n, max_tokens_per_doc (default 4096)}` → `{id, results: [{index, relevance_score}], meta: {billed_units: {search_units}}}`. **No** `return_documents` and **no** echoed `document` (`return_documents` a silent no-op, `ScoredDocument.document` null); `search_units` → `RerankUsage.search_units`; no fail-loud truncation. **`/v2/embed`:** `{model, input_type (**required**; enum `search_query` / `search_document` / `classification` / `clustering` / `image` — re-verified 2026-07-12; only `image` carries a model-version restriction), texts (max 96), embedding_types (default ["float"]), truncate (NONE/START/END), output_dimension (embed-v4+)}` → `{id, embeddings: {float: [[...]]} keyed by type, texts, meta: {billed_units: {input_tokens}}}`. `input_type` mandatory (OA absent → `search_document`). Per proposal 0099 the §8.4 mapping recognizes OA `query` / `document` / `classification` / `clustering` (the last two identity-mapped); `image` is **not** recognized (an input modality, not a purpose for embedded text). `embedding_types` is mapping-managed: an extras-supplied value is merged with the mandatory `"float"`, never replacing it. `truncate: NONE` fail-loud; 96-input per-call cap → client-side chunk-and-stitch; no top-level `model`. Both endpoints: errors `401`/`404`/`400`/`429`/`5xx` (Cohere does not use `422`). |
| [Langfuse SDK](https://github.com/langfuse/langfuse-python) | v4.x line (verified v4.7.1) | Stable v4.x | 2026-08-08 | Used by observability §8 Langfuse mapping. v5 announcement watched; `set_current_trace_io` marked deprecated in v4 per observability §8.4.1 caveat. The v4 SDK maintains a **process-wide client keyed by public key** (`LangfuseResourceManager`): a later construction for a key already present returns the cached client and **discards** a newly supplied `TracerProvider` — the behavior observability §6's Langfuse payload-leak invariant addresses (proposal 0116; verified against the v4 **Python** SDK source 2026-08-08, the SDK this row links to). |
| [JSON Schema](https://json-schema.org/specification) | draft-2020-12 | Released (latest draft) | 2026-05-31 | Used in llm-provider §4 `Tool.parameters` and §5 `response_schema`. |
| [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119) — keyword conventions | RFC 2119 (Best Current Practice) | Published | 2026-05-31 | MUST / SHOULD / MAY usage across normative spec text. |
| [RFC 2397](https://datatracker.ietf.org/doc/html/rfc2397) — data URI scheme | RFC 2397 | Published | 2026-05-31 | Used by llm-provider §3.1.3 inline-image source shape. |

## Per-dependency detail

### OpenTelemetry semantic conventions

OpenArmature observability §3–§7 reference the OpenTelemetry semantic
conventions for cross-vendor attribute naming. The semconv has a
per-attribute stability model — individual attributes carry their own
status (Stable, Development, Experimental, Deprecated) independent of the
release tag.

**The GenAI semconv moved and is wholly Development.** As of 2026-06-17 the
GenAI semantic conventions live in the dedicated
[`semantic-conventions-genai`](https://github.com/open-telemetry/semantic-conventions-genai)
repository, where the **entire `gen_ai.*` surface is Development** (registry
`model/gen-ai/registry.yaml`: 96 attributes Development, none Stable), and
`gen_ai.system` has been **removed upstream in favor of `gen_ai.provider.name`**
(also Development). `error.type` is part of the core semconv, not the GenAI
surface, and remains Stable.

OA's adoption pattern (per [Governance — External-dependency adoption](governance.md):
the *de-facto-standard carve-out* + *post-adoption retention* rules):

- **Core de-facto-standard `gen_ai.*` names — adopted directly** even at upstream
  Development, because every GenAI-aware backend keys on them and an
  `openarmature.*` mirror would defeat that recognition: `gen_ai.request.model`,
  `gen_ai.response.model`, `gen_ai.usage.input_tokens`,
  `gen_ai.usage.output_tokens`, `gen_ai.response.id`,
  `gen_ai.response.finish_reasons`, the §5.5.2 request parameters, and
  `gen_ai.system` (retained — see below). The deciding line is installed-base
  recognition, not the upstream maturity label.
- **`gen_ai.system` — retained.** Upstream removed it in favor of
  `gen_ai.provider.name` (Development). Per the post-adoption retention rule OA
  keeps emitting `gen_ai.system` (observability §5.5.3 / §5.5.8 + the §8.4.3
  Langfuse mapping; the installed base still keys on it); migration to
  `gen_ai.provider.name` is deferred to a future proposal.
- **Peripheral Development attributes — mirrored** to the `openarmature.*`
  namespace until they are Stable or demonstrably ubiquitous. The cache-token
  attributes (`gen_ai.usage.cache_read.input_tokens` /
  `gen_ai.usage.cache_creation.input_tokens`) use
  `openarmature.llm.cache_read.input_tokens` /
  `openarmature.llm.cache_creation.input_tokens` (observability §5.5.3.1).
  `gen_ai.operation.name` (well-known values `"chat"`, `"embeddings"`, …) is not
  adopted; operation discrimination is via span name + provider (observability
  §5.5 `openarmature.llm.complete` for LLM completion and §5.5.8
  `openarmature.embedding.complete` for embedding). A follow-on MAY adopt either
  directly once it is Stable or demonstrably ubiquitous, per the §5.5.3.1 / 0047
  mirror pattern.
- **Tool-call request rendering — OA-namespace (verified for proposal 0076).** The model's
  *requested* tool calls are surfaced as flat OA-namespace attributes
  (the gated `openarmature.llm.output.tool_calls` serialization + the ungated
  `openarmature.llm.output.tool_calls.count` / `.names` / `.ids` projections, observability
  §5.5.1 / §5.5.10), with no
  upstream `gen_ai.*` equivalent to adopt: the GenAI registry carries output tool calls as
  `tool_call` *parts* inside the structured `gen_ai.output.messages` attribute (not a flat
  per-request surface), and the `gen_ai.tool.*` family (`gen_ai.tool.name`,
  `gen_ai.tool.call.{id,arguments,result}`, `gen_ai.tool.definitions`, …) is scoped to the separate
  `execute_tool` span — the tool-*execution* side, not the chat-completion span. Verified against the
  `semantic-conventions-genai` registry, 2026-06-19.
- **Tool-execution span — `openarmature.tool.*` mirror (verified for proposal 0063).** OA's
  tool-execution observability (observability §5.5.11) emits OA-namespace `openarmature.tool.*`
  attributes and the span name `openarmature.tool.call`, mirroring the upstream `execute_tool` span +
  `gen_ai.tool.*` attributes — which are **Development** (verified 2026-06-19) and, under the
  de-facto-standard carve-out, assessed **peripheral** (the tool-execution surface lacks the
  installed-base recognition of the core completion attributes; upstream itself directs manual
  instrumentation). A follow-on adopts `gen_ai.tool.*` (a prefix swap) when the surface reaches
  recognized-core / Stable. The failure `error.type` is Stable core, used directly.
- **GenAI metric instruments — mirrored (verified for proposal 0067).** The upstream GenAI metric
  instruments `gen_ai.client.token.usage` (`{token}`) and `gen_ai.client.operation.duration` (`s`) are
  Development (verified 2026-06-19); OA emits `openarmature.gen_ai.client.*` mirrors (instrument type /
  unit / bucket advisory) per observability §11.2, the instrument-name cutover deferred to a Stable
  follow-on. The metric dimensions follow the same core-vs-peripheral split as the §5.5 span
  attributes (`gen_ai.request.model` / `gen_ai.system` core-direct, the latter retained;
  `gen_ai.operation.name` / `gen_ai.token.type` peripheral → `openarmature.gen_ai.*`; `error.type`
  Stable-direct).

### LLM provider APIs (OpenAI / Anthropic / Google Gemini)

These APIs do not semver their wire shapes. They version via:

- **URL path** (e.g., `v1` for OpenAI / Gemini)
- **Header date** (e.g., `anthropic-version: 2023-06-01`)
- **Model identifier** (e.g., `gpt-4o-2024-08-06`, `claude-sonnet-4-5`)

Per-row "Last verified" dates carry the drift-detection weight for these
dependencies. The wire mappings under llm-provider §8.X are written against
the API shape verified as of that date; spec proposals that update an
existing §8.X mapping include a re-verification step.

### Langfuse SDK

Langfuse has a public Python SDK that OA's observability §8 Langfuse mapping
implementations rely on. The SDK semvers; OA tracks the latest stable v4.x
release.

A vendor-side deprecation of `set_current_trace_io` / `Span.set_trace_io`
(used to populate `trace.input` / `trace.output` per §8.4.1) is documented
in observability §8.4.1 (caveat paragraph). When Langfuse v5 ships, OA
re-verifies the §8 mapping; if the migration requires normative spec
changes, a follow-up proposal lands.

The v4 SDK's client resource manager is a **process-wide singleton keyed by
public key**: the first construction for a key binds and caches the client
(including whatever `TracerProvider` it is given); a later construction for the
same key returns the cached client and ignores a newly supplied provider. This
is load-bearing for observability §6's mode-(b) Langfuse payload-leak invariant
(proposal 0116) — it is why openarmature's own isolated `TracerProvider` can be
silently discarded when the application constructed a same-key client first, and
why §6's detection is best-effort (reading the client's bound provider rests on
non-portable SDK internals). Verified against the v4 SDK source 2026-08-08; a v5
transition re-verifies it alongside the §8 mapping.

Reading the bound provider is the one private-surface dependence the **normative
text** rests on, which is why it is the only one named here. An implementation
generally reaches further into the SDK to realize the §8 mapping, and what each
one depends on is published under
[Implementation support](#implementation-support).

## Implementation support

The matrix above is a spec fact. This section is an implementation fact, and the
two are kept apart deliberately: "the Langfuse mapping is written against the v4
SDK line and verified at 4.7.1" is true of the specification, while "this
implementation resolves anywhere in `>=4.6,<5` but has verified 4.7.1" is true
only of that implementation. A second implementation carrying entirely different
numbers would be equally conforming.

Each row is published by the implementation itself, in the same conformance
manifest that drives the Python column on the [Proposals](proposals.md) index.
Nothing here is hand-maintained, and no number here is copied from the matrix
above.

**Reading the columns.** *Requires* is the version range the implementation
publishes to its own consumers, so it is the range a dependency resolver is free
to pick from. *Verified* is the single version the implementation has actually
exercised, and *Verified on* is when that pin was last deliberately moved or
re-verified. A *Requires* range reaching well past *Verified* is ordinary and is
not by itself a defect; it is simply the gap worth knowing about before assuming
an untested upper bound behaves.

*Verified on* is deliberately not refreshed by a passing test run, so an old
date means the pin has genuinely not moved rather than that nobody updated the
page. Read a date sitting well behind a still-widening *Requires* range as the
signal it is: the untested part of that range has been growing.

**Internals** counts the private, unsupported surface of the dependency that the
implementation reaches into. Private surface carries no compatibility guarantee
and can be renamed or removed in a patch release, so an implementation depending
on it is expected to guard that surface in its own test suite rather than
discover a rename in production. The count is published because the exposure is
worth seeing, not because it is a fault: some upstream capabilities have no
public equivalent.

<!-- BEGIN GENERATED: implementation-dependencies -->
<!-- Regenerated by scripts/regenerate_impl_dependencies.py from each implementation's published conformance manifest. Edits between the markers are overwritten. -->

| Implementation | Dependency | Requires | Verified | Verified on | Internals |
|---|---|---|---|---|---|
| openarmature-python | Langfuse SDK | `>=4.6,<5` | `4.7.1` | 2026-08-13 | 10 |

Implementation notes:

- **openarmature-python / Langfuse SDK:** The declared range currently resolves as far as 4.14.x, well past `verified`. Every listed internal still exists there and the suite passes against it, but 4.7.1 is the version this implementation deliberately tests against. Losing one of these internals does not raise to the caller: the graph observer isolates observer errors, so an observation simply stops being emitted and a leak assertion reads clean, which is why they are guarded rather than trusted.

??? note "openarmature-python: Langfuse SDK private surface (10 paths)"

    - `langfuse._client.client.Langfuse._resources`
    - `langfuse._client.client.Langfuse._tracing_enabled`
    - `langfuse._client.client.Langfuse._otel_tracer`
    - `langfuse._client.client.Langfuse._create_remote_parent_span`
    - `langfuse._client.resource_manager.LangfuseResourceManager.tracer_provider`
    - `langfuse._client.resource_manager.LangfuseResourceManager._instances`
    - `langfuse._client.span.LangfuseGeneration`
    - `langfuse._client.span.LangfuseTool`
    - `langfuse._client.span.LangfuseEmbedding`
    - `langfuse._client.span.LangfuseRetriever`

<!-- END GENERATED: implementation-dependencies -->

## Maintenance

### When to update this page

- An OA proposal adds or changes a normative reference to an external
  artifact (the proposal's Accept-phase work includes a row update or new
  row, plus refreshing the page-level **Last refreshed** date).
- A periodic re-verification round confirms the existing rows still match
  current upstream documentation (the per-row "Last verified" date updates
  in place; if drift is detected, a follow-up proposal addresses the
  change).
- An upstream announcement (e.g., the Langfuse SDK v4 → v5 transition)
  warrants pre-emptive tracking. Drift discovered between verifications
  is logged with an additional note rather than silently absorbed.

**Move the column, not just the note.** A proposal that re-verifies an
upstream fact and records the date in a row's Notes cell must advance that
row's **Last verified** column to match, and the page-level **Last
refreshed** date with it. Writing the date into the prose and leaving the
column behind makes the row contradict itself and understate the work done.
`scripts/validate_compatibility_dates.py` enforces both, and CI runs it. It
recognizes a date in a Notes cell only when **verification wording introduces
it** ("verified 2026-08-08", "re-verified against the OpenAPI 2026-08-08"), so
that a date belonging to a version identifier or a model name is not mistaken
for a verification. Phrase a re-verification that way, or the check has nothing
to match and the contradiction ships.

### Verification cadence guidance

Per-dependency drift rates vary; suggested starting cadences:

- **LLM provider APIs** (OpenAI / Anthropic / Gemini): quarterly, plus
  any spec proposal touching the relevant §8.X mapping.
- **OpenTelemetry semconv**: per upstream release-tag bump (the upstream
  publishes a [release feed](https://github.com/open-telemetry/semantic-conventions/releases)
  worth watching).
- **Vendor SDKs** (Langfuse, etc.): per upstream minor release.
- **IETF RFCs** (2119, 2397, etc.): opportunistic — these rarely change.

These are starting points, not rules. Adjust as the dependency's actual
drift rate becomes apparent.

### Refreshing the implementation-support block

The [Implementation support](#implementation-support) block is generated, not
maintained here. To change what it says, change the publishing implementation's
conformance manifest; to refresh what this page renders from it, run
`scripts/regenerate_impl_dependencies.py`. Because the block reads each
implementation's live default branch, an implementation can make this page
stale with no commit in this repository, so CI checks it on every pull request
touching markdown and on a weekly schedule. The remedy is a regeneration, never
a hand edit.

### How to add a new dependency

When OA's spec adds a new normative reference to an external artifact:

1. **Add a row to the compatibility matrix.** Required columns: dependency
   name (with link), OA-tracked version / scope, upstream status, last
   verified date (today), notes (which spec sections reference it, any
   adoption nuances).
2. **Add a per-dependency detail section** under *Per-dependency detail*
   if the adoption has nuance — per-attribute stability rules, partial
   adoption, vendor-specific framing, etc. Simple dependencies (a single
   stable artifact) can stay matrix-only.
3. **Refresh the page-level Last refreshed date** at the top of this
   page.
4. **Cite the new entry** in the proposal text that added the reference
   (the proposal links to this page for the operational tracking; the
   normative reference itself lives in the spec text).

The page is freely editable per the governance "charter / docs" carve-out
([Governance](governance.md)) — small re-verification updates do not
require a proposal. Normative spec changes that flow from a re-verification
(e.g., adopting a newly-Stable upstream attribute) DO require a proposal
per the standard discipline.
