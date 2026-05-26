# 0031: Observability — Langfuse Backend Mapping

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-26
- **Accepted:**
- **Targets:** spec/observability/spec.md (adds §8 *Langfuse mapping*; renumbers existing §8 *Determinism* → §9, §9 *Out of scope* → §10)
- **Related:** 0007 (observability OTel span mapping), 0017 (prompt-management core), 0024 (LLM span payload and GenAI semconv)
- **Supersedes:**

## Summary

Add a sibling **Langfuse backend mapping** to the observability spec, alongside
the OpenTelemetry mapping already specified in §3–§7. The new §8 normatively
maps the §6 observer event stream onto Langfuse's data model — Traces,
Observations (Generation, Span, Event), and the SDK's native prompt-linkage
entity — so a LangfuseObserver writes Langfuse-shaped data directly instead
of mirroring OTel attributes through Langfuse's OTLP ingest. The mapping
covers: which OA span types map to which Langfuse observation types
(invocation → Trace, node/subgraph/fan-out → Span observation, LLM provider
→ Generation observation); the attribute-key translation table from OA's
`openarmature.*` namespace and the GenAI semconv `gen_ai.*` namespace onto
Langfuse's `metadata` and observation-shape fields; correlation ID
realization on trace and observation metadata; the `langfuse.trace.name`
attribute on the Trace and where its value sources from; generation
rendering with payload + truncation reuse from §5.5; prompt linkage that
attaches a Langfuse Prompt entity reference when the prompt's source
provides one (regardless of which specific backend produced it) and
falls back to metadata-only otherwise; and
composition rules so a graph wired to BOTH the OTel observer AND the
Langfuse observer produces consistent OA-state across both backends. No
existing OTel-mapping behavior changes; the LangfuseObserver is a new
sibling consumer of the same §6 event stream. The OTel mapping remains
the reference shape for cross-backend equivalence (§1).

## Motivation

The v0.7.0 spec stood up §1's framing — the observability capability is a
substrate-neutral mapping family, with the OTel mapping (§3–§7) as the
first concrete backend. §9 (becoming §10 in this proposal) names Langfuse
as a deferred mapping. Two real-world signals justify landing it now:

1. **Production deployments today rely on Langfuse's OTLP ingest with
   custom per-service attribute-mapping shims.** The pattern recurs
   across reported usage of the v0.17.0 LLM-payload + GenAI semconv
   attributes (proposal 0024): on the observability side, a per-service
   attribute mapper translating `openarmature.prompt.*` →
   `langfuse.prompt.*` and `openarmature.llm.*` →
   `langfuse.observation.*` so Langfuse renders generations correctly;
   on the prompt-management side, a thin wrapper around the Langfuse
   client. Each adopter re-derives the same shim, and each shim's
   correctness is fragile under evolving Langfuse OTLP ingest
   semantics. A normative mapping replaces the shim with a first-class
   LangfuseObserver.

2. **Langfuse's native data model carries more than OTel can.** Generation
   observations have first-class `input`, `output`, `model`,
   `modelParameters`, `usage`, and `prompt` (Prompt-entity link) fields.
   The OTel mirroring approach uses `langfuse.observation.input` /
   `.output` and `langfuse.prompt.name` / `.version` flat-string OTel
   attributes that Langfuse's ingest parses back into the native shape.
   That translation is lossy on the Generation `prompt` link (the OTel
   path can only carry name+version+label, not a true entity link), and
   it requires the user to remember the exact attribute names Langfuse's
   ingest expects this season. A LangfuseObserver that calls the
   Langfuse SDK directly produces clean native shape without the
   round-trip.

Proposal 0024 explicitly deferred a Langfuse-native backend mapping
(see its "Why now" section) precisely so the LLM-payload work could
ship without bundling the larger Langfuse surface. This proposal lands
that deferred work and, in doing so, addresses one specific OTLP-mirror
wart: Langfuse's OTLP ingest does not derive the Langfuse Trace's
display name from the OTel root span name; it reads a Langfuse-specific
attribute. A native LangfuseObserver sets the Trace's name field
directly through Langfuse's Trace API and sidesteps the attribute-key
guessing game.

A normative Langfuse mapping has three concrete benefits, paralleling
the original OTel-mapping rationale (§7 of proposal 0007):

1. **Cross-implementation parity.** Python and TypeScript implementations
   of the LangfuseObserver produce equivalent Langfuse traces — same
   observation hierarchy, same metadata keys, same Generation shape.
2. **Removes the per-service shim.** Users delete their attribute-mapping
   middleware; the framework's Langfuse output is correct out of the box.
3. **OTel mapping remains the reference.** Cross-backend equivalence
   (§1) means a span emitted to OTel and a Span/Generation observation
   emitted to Langfuse describe the same node execution; users who
   attach both observers see the same OA state in both backends, joined
   by `correlation_id`.

### Why now

Production demand for first-class Langfuse emission has been building
since the v0.17.0 LLM-payload + GenAI semconv work shipped; adopters of
that work hit the OTLP-ingest-plus-shim friction immediately. The
predecessor proposal (0024) is now stable, so the attribute set this
mapping translates from is fixed; no additional predecessors gate this
work.

## Design

The full proposed text of the new §8 of `spec/observability/spec.md` is
reproduced below. The §-numbering for existing sections shifts:
current §8 (Determinism) becomes §9; current §9 (Out of scope) becomes
§10. The renumbered §9 / §10 content is unchanged.

The spec version under which this lands is determined at acceptance
time and recorded in `CHANGELOG.md`. Anticipated bump: MINOR
(v0.23.0) — new spec section, no breaking changes to §1–§7.

---

### 8. Langfuse mapping

This section specifies the **Langfuse** backend mapping, sibling to the
OpenTelemetry mapping in §3–§7. Implementations that emit Langfuse data
directly (a "Langfuse observer") follow the rules below. The mapping
consumes the same §6 observer event stream as the OTel mapping — a graph
MAY have both observers attached, and each one is a self-contained
consumer of the event stream.

The OTel mapping remains the reference shape for cross-backend
equivalence (§1). When a graph is wired to BOTH observers, the same
OA-state appears in both backends; users join by `correlation_id` (§3)
to follow a single invocation across them.

#### 8.1 Purpose

The Langfuse mapping defines how OA's runtime event surface maps to
Langfuse's native data model — Traces, Observations (Generation, Span,
Event), and the Prompt entity — without going through Langfuse's OTLP
ingest. Direct emission via the Langfuse client preserves the full
fidelity of Langfuse's native shape (first-class Generation rendering,
true Prompt-entity links, Langfuse-shaped metadata) where OTLP-then-ingest
produces lossy translation through string-valued OTel attributes.

This mapping covers the Trace + Observation surface. Langfuse Sessions,
Scoring, and Cost surfaces are deferred (§8.10).

#### 8.2 Langfuse data model

Langfuse exposes a small set of entity types relevant to this mapping:

- **Trace.** Top-level container for one logical interaction. Carries
  identity (`id`), metadata (`name`, `userId`, `sessionId`, `tags`,
  `version`, arbitrary `metadata` map), and contains a tree of
  Observations.
- **Observation.** A unit of work nested under a Trace. Three concrete
  types:
  - **Span.** Generic timed work — node executions, subgraph dispatch,
    fan-out dispatch.
  - **Generation.** LLM call. Adds `input`, `output`, `model`,
    `modelParameters`, `usage`, `prompt` (link to a Prompt entity) on
    top of the base Span fields.
  - **Event.** Point-in-time signal with no duration. Not used by this
    mapping; reserved for future proposals.
- **Prompt entity.** A Langfuse-managed prompt record with `name`,
  `version`, `label`, and content. Generation observations carry a
  native link to a Prompt entity when the prompt's source provides one
  (see §8.4.4 for the linkage trigger).

Implementations consume Langfuse's client SDK in their host language
(Python, TypeScript). The SDK calls themselves are impl detail; this
mapping constrains the **shape that lands in Langfuse**, not the SDK
method names.

#### 8.3 Observation-type mapping

Each OA span type (per §4 of the OTel mapping) translates to a Langfuse
entity per the table below.

| OA span type | Langfuse entity |
|---|---|
| Invocation span (§4) | Trace (the container itself; no top-level Span observation wraps it) |
| Node span (§4) | Span observation, child of the Trace or the surrounding parent Span |
| Subgraph span (§4.3) | Span observation, child of the surrounding parent Span; contains the subgraph's nested node Span observations |
| Fan-out node span (§4) | Span observation (the dispatch span; contains the per-instance Span observations) |
| Fan-out instance span (§4.3) | Span observation, child of the fan-out node Span |
| LLM provider span (§5.5) | Generation observation |
| Retry attempt spans (§4) | Sibling Span / Generation observations (one per attempt) under the same parent; per-attempt attribution uses the metadata.attempt_index key (§8.4) |

The invocation maps to the Trace (the container) rather than to a
top-level Span observation. Rationale: Langfuse's Trace IS the root
container; introducing an additional Span observation under the Trace
duplicates the root and creates an extra layer the UI must render. The
trace-level metadata fields (§8.4) carry the OA invocation attributes
that would otherwise live on a root span.

#### 8.4 Attribute mapping table

The §5 OA attribute keys translate to Langfuse fields per the tables
below. Implementations MUST set the corresponding Langfuse fields when
the source OA attribute is set on the source span (per §5).

##### 8.4.1 Trace-level mapping (sourced from invocation span attributes)

| OA attribute (per §5.1, §5.6) | Langfuse Trace field |
|---|---|
| `openarmature.invocation_id` | `trace.id` (UUIDv4; MUST use the invocation_id verbatim as the Trace ID, so cross-system lookup by invocation_id finds the Langfuse Trace) |
| `openarmature.correlation_id` | `trace.metadata.correlation_id` AND propagated to every observation's `metadata.correlation_id` per §8.5 |
| `openarmature.graph.entry_node` | `trace.metadata.entry_node` |
| `openarmature.graph.spec_version` | `trace.metadata.spec_version` |
| (caller-supplied invocation label OR entry node name, per §8.6) | `trace.name` |

##### 8.4.2 Observation-level mapping (sourced from node / subgraph / fan-out span attributes)

| OA attribute (per §5.2, §5.3, §5.4, §5.6) | Langfuse Observation field |
|---|---|
| `openarmature.node.name` | `observation.name` |
| `openarmature.node.namespace` | `observation.metadata.namespace` (string array preserved as-is) |
| `openarmature.node.step` | `observation.metadata.step` |
| `openarmature.node.attempt_index` | `observation.metadata.attempt_index` |
| `openarmature.node.fan_out_index` | `observation.metadata.fan_out_index` (when present) |
| `openarmature.subgraph.name` | `observation.metadata.subgraph_name` (when present) |
| `openarmature.fan_out.item_count` | `observation.metadata.fan_out_item_count` (fan-out node Span observation only) |
| `openarmature.fan_out.concurrency` | `observation.metadata.fan_out_concurrency` (fan-out node Span observation only) |
| `openarmature.fan_out.error_policy` | `observation.metadata.fan_out_error_policy` (fan-out node Span observation only) |
| `openarmature.fan_out.parent_node_name` | `observation.metadata.fan_out_parent_node_name` (fan-out instance Span observation only) |
| `openarmature.correlation_id` | `observation.metadata.correlation_id` (cross-cutting per §8.5) |
| `openarmature.error.category` | `observation.level = "ERROR"`, `observation.statusMessage = <category>` |

##### 8.4.3 Generation-specific mapping (sourced from LLM provider span attributes)

Generation observations inherit the §8.4.2 observation-level mapping
above (name, metadata.*, level/statusMessage). The fields below are
additional, specific to Generations.

| OA attribute (per §5.5) | Langfuse Generation field |
|---|---|
| `openarmature.llm.model` (and `gen_ai.request.model`) | `generation.model` |
| Each `gen_ai.request.*` request-parameter attribute defined in §5.5.2 | `generation.modelParameters.<suffix>` — the §5.5.2 attribute's suffix after `gen_ai.request.` becomes the key under `modelParameters` (e.g., `gen_ai.request.temperature` → `modelParameters.temperature`). Emitted only when the source attribute is set. As §5.5.2 evolves to add further request-parameter attributes, the Langfuse `modelParameters` set expands by inclusion without further §8.4.3 edits. |
| `openarmature.llm.input.messages` (when payload enabled per §5.5.4) | `generation.input` (parsed back from the JSON-encoded OA attribute string to the native message-list structure) |
| `openarmature.llm.output.content` (when payload enabled per §5.5.4) | `generation.output` |
| `openarmature.llm.request.extras` (when payload enabled per §5.5.4) | `generation.metadata.request_extras` (the JSON-encoded OA attribute parsed back to a native object) |
| `openarmature.llm.usage.prompt_tokens` (and `gen_ai.usage.input_tokens`) | `generation.usage.input` (Langfuse Usage record's input field) |
| `openarmature.llm.usage.completion_tokens` (and `gen_ai.usage.output_tokens`) | `generation.usage.output` |
| `openarmature.llm.usage.total_tokens` | `generation.usage.total` |
| `openarmature.llm.finish_reason` (and `gen_ai.response.finish_reasons[0]`) | `generation.metadata.finish_reason` |
| `gen_ai.system` | `generation.metadata.system` |
| `gen_ai.response.model` (when set) | `generation.metadata.response_model` |
| `gen_ai.response.id` (when set) | `generation.metadata.response_id` |

When a generation's finish_reason is an error condition (e.g.,
`"content_filter"`, `"length"` — vendor-specific), the implementation
MAY also set `observation.level = "WARNING"` to surface the condition
in the Langfuse UI; this is RECOMMENDED but not MUST (different
vendors carry different "soft error" semantics, and the OA error
category mechanism in §4.2 covers hard failures via the
`openarmature.error.category` mapping above).

##### 8.4.4 Prompt linkage mapping (sourced from prompt-management §11 attributes)

When the LLM provider span carries `openarmature.prompt.*` attributes
(per prompt-management §11), the Generation observation MUST surface
the prompt identity. The mechanism depends on what the prompt's source
backend provides — not on which specific backend it is. Two cases:

1. **The prompt's source exposes a Langfuse Prompt reference.** Any
   prompt backend that attaches an accessible Langfuse Prompt entity
   to the rendered prompt qualifies. A Langfuse-native PromptBackend
   is the obvious case, but the contract is open to other backends
   that may expose the same — e.g., a federated proxy backend that
   resolves through Langfuse, a custom backend that mirrors prompts
   to Langfuse, or any future backend that interoperates with the
   Langfuse Prompt entity. In all such cases the Generation
   observation MUST be linked to that Langfuse Prompt entity via
   Langfuse's native link mechanism (the Generation API accepts a
   prompt reference; the SDK call shape is impl detail). The metadata
   fields below MUST also be set redundantly so consumers can query
   without traversing the link.
2. **The prompt's source does NOT expose a Langfuse Prompt
   reference.** This covers all backends that have no native Langfuse
   Prompt counterpart — filesystem, in-memory, and any other
   non-Langfuse-aware backend (current or future). No Prompt-entity
   link is established; identity surfaces via metadata only.

The trigger for case 1 versus case 2 is whether a Langfuse Prompt
reference is available on the prompt record at emission time. How that
reference is exposed — a metadata field on `Prompt`, an interface
marker, an SDK-side accessor — is the prompt-management capability's
concern (implementation-defined under prompt-management §3's `metadata`
mapping). The Langfuse observer MUST establish the link when a
reference is present and MUST NOT fabricate one when absent.

In both cases the following metadata is set:

| OA attribute (per prompt-management §11) | Langfuse Generation field |
|---|---|
| `openarmature.prompt.name` | `generation.metadata.prompt.name` |
| `openarmature.prompt.version` | `generation.metadata.prompt.version` |
| `openarmature.prompt.label` | `generation.metadata.prompt.label` |
| `openarmature.prompt.template_hash` | `generation.metadata.prompt.template_hash` |
| `openarmature.prompt.rendered_hash` | `generation.metadata.prompt.rendered_hash` |

The `generation.metadata.prompt` map's shape is normative for
cross-implementation parity. Implementations MUST NOT collapse it into
flat metadata keys (e.g., `metadata.prompt_name` flat strings) when
the structured shape above is available — the structured form lets
Langfuse UI extensions render prompt identity uniformly.

**Prompt-group propagation.** When `openarmature.prompt.group_name`
is set on spans participating in a `PromptGroup` (per prompt-management
§9 / §11), the value propagates to
`observation.metadata.prompt_group_name` on every participating
observation — including each Generation observation for the group's
LLM calls and any wrapping node/subgraph Span observations carrying
the group_name. Unlike the per-Generation prompt-identity fields
above, this is an observation-level attribute and follows the §8.4.2
observation-level mapping pattern.

#### 8.5 Correlation ID realization

The cross-backend correlation ID (§3) surfaces in Langfuse at two
levels:

- **Trace-level metadata.** Each Trace's `metadata.correlation_id` MUST
  carry the invocation's correlation ID. Users querying Langfuse for
  traces matching a correlation ID found in their OTel logs filter
  here.
- **Observation-level metadata.** Each Observation (Span, Generation)
  MUST also carry `metadata.correlation_id`. Observations from detached
  subgraphs and detached fan-outs (per §4.4) live in separate Traces
  but share the same correlation ID with the parent invocation;
  observation-level metadata lets users filter across all of them in
  one query without first finding the related Traces.

Detached trace mode (§4.4) applies to the Langfuse mapping the same as
to the OTel mapping. A detached subgraph or fan-out produces a separate
Langfuse Trace (new `trace.id`); the parent's dispatch observation
carries a Langfuse-native cross-trace reference in its metadata
(`metadata.detached_child_trace_ids` — string array, one entry per
detached child). The correlation_id is invocation-scoped per §3, so
all detached Traces and the parent Trace share the same
`metadata.correlation_id`.

#### 8.6 Trace name

The Langfuse Trace MUST carry a `trace.name` field. This is the human-
readable identifier the Langfuse UI surfaces in trace lists and
search results; meaningful trace names are how users find their work
in the UI.

The trace-name source is one of:

1. **Caller-supplied invocation label.** Implementations MUST support
   a per-invocation caller-supplied label that maps to `trace.name`.
   The mechanism (keyword argument to `invoke()`, field on the
   invocation config record, equivalent per-language convention) is
   implementation-defined; the behavioral contract is that the caller
   has a way to set it.
2. **Entry-node name fallback (RECOMMENDED default).** When the caller
   supplies no invocation label, implementations SHOULD default
   `trace.name` to the graph's entry-node name (already exposed via
   `openarmature.graph.entry_node`). Falling back to entry-node name
   gives Langfuse traces a meaningful default label without requiring
   callers to thread an extra argument through every `invoke()` call.

Implementations MAY support additional sources (e.g., a registered
trace-name resolver function on the observer) at their discretion;
the behavioral contract above is the minimum.

#### 8.7 Generation rendering

Generation observations render the LLM call's input/output content
when the Langfuse observer's `disable_llm_payload` flag is `False`.
The flag governs Langfuse-side emission only; it is independent of
the OTel observer's flag per §8.9. Both observers consume the same
source data (per §5.5's definition of LLM-payload content) from the
§6 LLM provider event, and each makes its own emission decision.

The Langfuse observer MUST support its own `disable_llm_payload` flag
independent of the OTel observer's setting (per §8.9). When the flag
is `False`, the observer:

- Parses the §5.5.1 `openarmature.llm.input.messages` JSON string back
  to the native message-list structure (per llm-provider §3 message
  shape) and sets `generation.input` to the parsed structure.
- Sets `generation.output` from `openarmature.llm.output.content`
  verbatim.
- Sets `generation.metadata.request_extras` from
  `openarmature.llm.request.extras` (parsed back from JSON).

When the flag is `True` (default), `generation.input`,
`generation.output`, and `generation.metadata.request_extras` MUST NOT
be set on the Generation observation. Other fields (model,
modelParameters, usage, metadata.system, metadata.response_model,
metadata.response_id, prompt linkage) continue to emit per §8.4.3 and
§8.4.4 regardless of the payload flag.

**Truncation contract.** The §5.5.5 per-attribute byte cap applies to
the OA-attribute source values; when the source attribute is
truncated, the Langfuse observer receives the already-truncated
string (the OTel and Langfuse observers MAY share the same truncation
implementation upstream). The Langfuse observer:

- Sets `generation.input` / `generation.output` /
  `generation.metadata.request_extras` to the truncated value as-is
  when the source string ends with the §5.5.5 truncation marker
  (`…[truncated, M bytes total]`). For `generation.input` and
  `generation.metadata.request_extras` (which are intended to be
  structured objects in Langfuse, not strings), the truncated form is
  not parseable JSON — the observer MUST set those fields to the
  raw truncated string in that case, preserving the marker; the
  Langfuse UI surfaces this as a string rather than a structured
  view. This matches the §5.5.5 design intent: the unparseable JSON
  IS the truncation signal.

**Inline-image redaction.** The §5.5.5 inline-image redaction rule
applies identically — inline image bytes never reach Langfuse, only
the placeholder `{type: "image", source: {type: "inline_redacted",
byte_count: N}, media_type, detail?}` record does. This is a hard
rule, ungated by `disable_llm_payload`.

#### 8.8 Prompt linkage

Per §8.4.4. The two cases (prompt source exposes a Langfuse Prompt
reference vs. does not) determine whether a Prompt-entity link is
established in addition to metadata. The metadata shape is normative
for cross-implementation parity; the link establishment is conditional
on the source's capability, not on any specific backend identity.

The propagation mechanism — how `openarmature.prompt.*` attributes
reach the LLM provider span at emission time — is the prompt-management
capability's concern (§11 of prompt-management; the mechanism is
implementation-defined). This mapping consumes the attributes once
they're on the span.

#### 8.9 Composition with OTel

The Langfuse observer and the OTel observer are independent §6 event
consumers. A graph MAY have both attached; both MAY emit during the
same invocation.

Each observer's behavior is governed by its own configuration:

- **`disable_llm_spans`** — each observer supports the flag
  independently. Setting `disable_llm_spans=True` on one observer
  does NOT suppress emission on the other. Use case: a user has
  external auto-instrumentation writing OTel spans for LLM calls and
  also wants the Langfuse observer to emit Generations natively; they
  set `disable_llm_spans=True` on the OTel observer (so OA doesn't
  duplicate the external library's spans) and leave it `False` on
  the Langfuse observer (so Generations still emit to Langfuse).

- **`disable_llm_payload`** — each observer supports the flag
  independently. A user MAY emit full payload to Langfuse (their
  canonical generation-rendering tool) while keeping OTel-side payload
  off (cost / size reasons). Defaults: `True` for OTel per §5.5.4,
  `True` for Langfuse for symmetric privacy posture.

- **`disable_genai_semconv`** — only meaningful to the OTel observer
  per §5.5.4. The Langfuse observer does not emit GenAI semconv
  attributes (it uses Langfuse-native fields); the flag is ignored
  by the Langfuse observer.

The cross-backend correlation ID (§3) is the join key. A user
filtering by `correlation_id` in Langfuse can find the same
`correlation_id` in their OTel logs (HyperDX, Datadog) and pivot
between the two views of one invocation.

**Unified Langfuse configuration.** Implementations SHOULD allow a
single Langfuse client configuration (host, public key, secret key,
or equivalent) to be shared across any Langfuse-consuming surfaces
the implementation exposes — the Langfuse observer, a Langfuse-aware
PromptBackend, and any future Langfuse-aware capability the
implementation adds. The API shape is impl-defined; the behavioral
contract is that the user configures Langfuse credentials once and
all Langfuse-consuming surfaces use them.

#### 8.10 Out of scope

Not covered by this section; deferred to follow-on proposals:

- **Langfuse Sessions.** Langfuse's `userId` / `sessionId` Trace fields
  support cross-trace grouping. Cross-invocation session identity is
  proposal 0020's concern; once that lands, `trace.sessionId`
  realization follows.
- **Langfuse Scoring.** Quality scoring of Generations / Traces is a
  separate surface that the OA spec does not currently address. A
  future `openarmature.score.*` attribute family and corresponding
  Langfuse `score` API call would land via a separate proposal.
- **Langfuse Cost / Custom token pricing.** Cost computation belongs
  to the Langfuse-side or to a future OA cost-tracking capability;
  this mapping uses Langfuse's standard `usage` shape only.
- **LangfusePromptBackend caching policy.** Backend-side caching is
  permitted by prompt-management §5 and is implementation-defined;
  this mapping does not constrain it.

---

## Spec edits beyond §8

This proposal also makes the following edits to existing sections:

- **§1 Purpose.** Update the closing paragraph from "This first version
  specifies the OpenTelemetry mapping. Future proposals add other
  backends (Langfuse, etc.) as sibling sections of this same spec; the
  OTel mapping serves as the reference shape for cross-backend
  equivalence." to acknowledge the Langfuse mapping as a sibling
  section; preserve the OTel-as-reference-shape line.
- **§2 Concepts.** Update the `Correlation ID` definition's example
  ("A user running an LLM workflow with both an OTel backend (system
  traces, logs) and a Langfuse backend (LLM-specific traces) uses the
  `correlation_id` as a join key…") to cross-reference §8.5 for the
  Langfuse realization.
- **§3.3 Backend-mapping contract.** Update the closing paragraph
  ("Future backend mappings (Langfuse, etc.) follow the same pattern:
  each spec section MUST include a 'correlation ID realization'
  subsection naming the field/attribute/metadata key the backend
  uses.") to point at §8.5 as the realization.
- **§9 (renumber from §8 Determinism).** The Determinism rules now
  apply to both mappings; the renumbered section adds one sentence
  affirming that Langfuse observation content is similarly a function
  of (a) the §6 event stream and (b) implementation-specific data
  (timestamps, observation IDs).
- **§10 (renumber from §9 Out of scope).** The "Langfuse mapping —
  separate proposal" bullet (line 832 of the current spec) is
  removed; the mapping now lives in §8.

All other sections (§3 cross-backend correlation, §4 OTel span
hierarchy, §5 OTel attribute namespace, §6 OTel span lifecycle, §7
OTel log correlation) are unchanged.

## Conformance fixtures

Three new fixtures land under `spec/observability/conformance/`
following the existing OTel-fixture numbering convention (the next
available numbers are 022, 023, 024):

- **022-langfuse-basic-trace.yaml + .md** — analogous to fixture 001
  (OTel basic trace). A three-node linear graph; verifies the
  invocation → Trace mapping, node → Span observation mapping, name
  derivation, and trace-level / observation-level metadata
  propagation. No LLM call.
- **023-langfuse-generation-rendering.yaml + .md** — analogous to
  fixture 013 (OTel LLM payload enabled). A graph with one LLM call
  and `disable_llm_payload=False` on the Langfuse observer; verifies
  Generation `input` / `output` / `model` / `modelParameters` /
  `usage` rendering; verifies the metadata-only fields (system,
  response_model, response_id, finish_reason). Payload truncation
  case asserted via a long-content variant.
- **024-langfuse-prompt-linkage.yaml + .md** — exercises both prompt-
  source cases. Case A: prompt sourced from a Langfuse-native
  PromptBackend → Generation has both the Prompt-entity link and the
  `metadata.prompt` map. Case B: prompt sourced from an in-memory /
  filesystem PromptBackend → Generation has the `metadata.prompt`
  map only, no Prompt-entity link.

The harness format (fixture header comment in 001) extends with:

- `langfuse_observer` block — configures the Langfuse observer
  (`disable_llm_payload`, `disable_llm_spans`, payload byte cap).
- `expected.langfuse_trace` — analogous to `expected.span_tree` but
  describing the Langfuse Trace + Observation tree shape.
- `prompt_backend.langfuse` — when a Langfuse-aware PromptBackend is
  in use (fixture 024 case A), the harness provides a mock backend
  that attaches canned Langfuse Prompt entity references to the
  prompts it returns; the fixture asserts the link is established on
  the resulting Generation observation.

The harness MAY use the same in-memory transport shape across both
the OTel and Langfuse observer paths; the conformance assertions
operate on the data captured by the harness's Langfuse-side
recorder, not on a real Langfuse API.

## Versioning

MINOR bump. The spec's whole-spec SemVer increments to **v0.23.0** on
acceptance:

- Adds a new spec section (§8) with normative behavior.
- Adds three conformance fixtures.
- Renumbers existing §8 → §9 and §9 → §10 (text unchanged beyond the
  numbering and one sentence added to the new §9 per "Spec edits
  beyond §8" above).
- No breaking changes to §1–§7. Implementations of the OTel mapping
  alone (no LangfuseObserver) continue to conform at v0.23.0 without
  modification.

CHANGELOG entry references this proposal.

## Out of scope

For this proposal specifically (in addition to the §8.10 deferrals
above):

- **TypeScript implementation.** No TS implementation of OA exists
  yet; cross-language parity testing happens when TS lands.
- **Implementation-side ergonomics.** The mapping describes shape, not
  SDK call sequences or constructor signatures. Implementations
  decide their own builder patterns, factory methods, and
  configuration surfaces.
- **Filesystem PromptBackend layout ergonomics, StrictUndefined
  opt-out config, Langfuse SDK compile() wrapping.** These are
  implementation-side ergonomic concerns; the spec contract is
  unchanged and these knobs are at each implementation's discretion.

## Open questions

1. **§8.6 trace-name default.** The proposed default is the entry-node
   name when no caller-supplied invocation label is provided. An
   alternative would be a constant default (`"openarmature.invocation"`,
   paralleling the OTel mapping's §4.5 constant). Picked the entry-node
   default because the OTel mapping's constant name was driven by OTel
   UI conventions; Langfuse trace lists are user-facing and benefit
   from differentiated names. Open for review.

2. **§8.4.4 prompt-metadata shape.** Proposed as a nested
   `metadata.prompt.{name, version, label, template_hash,
   rendered_hash}` map. An alternative is flat keys
   (`metadata.prompt_name`, `metadata.prompt_version`, etc.). Picked
   the nested shape because it parallels the structure Langfuse uses
   for its own native prompt linkage and makes UI extensions easier to
   write. Open for review.

3. **§8.9 unified-config normativity.** The proposed text is
   "implementations SHOULD allow a single Langfuse client
   configuration… to be shared" — SHOULD, not MUST. Treating it as
   informative guidance rather than mandate because the shared-config
   requirement is impl-level ergonomics, not behavioral contract.
   Open for review on whether to upgrade to MUST.
