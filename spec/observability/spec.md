# Observability

Canonical behavioral specification for the OpenArmature observability capability.

- **Capability:** observability
- **Introduced:** spec version 0.7.0
- **History:**
  - created by [proposal 0007](../../proposals/0007-observability-otel-span-mapping.md)
  - §5.5 extended with LLM input/output payload attributes (default-off), `RuntimeConfig` request parameters under the OpenTelemetry GenAI semantic conventions, a minimum set of GenAI semconv response attributes, two new opt-out flags (`disable_llm_payload`, `disable_genai_semconv`), and a per-attribute truncation contract (64 KiB default cap, UTF-8-boundary-safe algorithm, 256-byte minimum, inline-image redaction) by [proposal 0024](../../proposals/0024-llm-span-payload-and-semconv.md)
  - §8 added — Langfuse backend mapping (sibling to the OTel mapping in §3–§7); covers observation-type mapping (invocation → Trace, node/subgraph/fan-out → Span observation, LLM provider → Generation observation), attribute translation from `openarmature.*` and `gen_ai.*` to Langfuse native fields, correlation ID realization on Trace + Observation metadata, `langfuse.trace.name` source, prompt linkage to a Langfuse Prompt entity when the prompt's source exposes one (falling back to metadata-only otherwise), and composition rules with the OTel observer; renumbers existing §8 Determinism → §9 and §9 Out of scope → §10 by [proposal 0031](../../proposals/0031-observability-langfuse-mapping.md)
  - §5.5.2 attribute list extended with three new GenAI semconv attributes (`gen_ai.request.frequency_penalty`, `gen_ai.request.presence_penalty`, `gen_ai.request.stop_sequences`) corresponding to the three new declared `RuntimeConfig` fields introduced by llm-provider [proposal 0032](../../proposals/0032-llm-provider-runtime-config-refinements.md). The §8.4.3 Langfuse-mapping reference to §5.5.2 expands by inclusion: the three new attributes flow into `generation.modelParameters.{frequency_penalty, presence_penalty, stop_sequences}` automatically, no §8 edit required.
  - §3 extended with new §3.4 *Caller-supplied invocation metadata* subsection — sibling caller surface to `correlation_id` accepting an arbitrary key/value mapping at `invoke()` time, propagated via the language's context primitive, augmentable mid-invocation via a framework helper (each fan-out instance gets its own per-async-context copy so per-instance additions don't leak to siblings), invocation-scoped (flows through detached subgraphs and fan-outs); §5.6 cross-cutting attribute family extended with `openarmature.user.*` (appears on every span and OTel log record, using the in-scope metadata at span emission time); §7 log records extended to carry the same family; §8.4.1 and §8.4.2 Langfuse propagation extended with caller metadata merged into `trace.metadata` and every `observation.metadata` as top-level keys (with a Langfuse-Sessions distinction note clarifying that this is orthogonal to Sessions/`sessionId`, which remain deferred to proposal 0020); graph-engine §3 gains a clarifying paragraph noting `invoke()` accepts the metadata mapping by [proposal 0034](../../proposals/0034-caller-supplied-invocation-metadata.md)
  - §5.6 cross-cutting attribute family extended with `openarmature.session_id` (appears on every span when the invocation is session-bound; same ambient-context propagation as `correlation_id`, absent otherwise); §7 log records extended to carry `openarmature.session_id` via the same OTel Logs Bridge mechanism; §7 detached-trace-mode paragraph extended to note `session_id` is invocation-scoped and unchanged across detached / parent traces by [proposal 0020](../../proposals/0020-sessions-capability.md)
  - §3.4 reserved-key enumeration extended with `branch_name`, `detached`, `detached_from_invocation_id` (24-name set total) — closes a coverage gap in 0041's reservation against the §8.4 Langfuse top-level metadata keys; §8.4.1 gains a `trace.metadata.detached_from_invocation_id` row (detached child trace's inverse pointer to the parent invocation); §8.4.2 gains `observation.metadata.branch_name` (per-branch Span observation) and `observation.metadata.detached` (dispatching observation flag) rows by [proposal 0042](../../proposals/0042-observability-reserved-keys-extension.md)
  - §8.2 Trace entity definition extends with `input` / `output` payload fields (documenting existing Langfuse Trace fields surfaced as headline columns); §8.4.1 gains `trace.input` and `trace.output` mapping rows + a *Trace input/output sourcing* paragraph defining the `disable_state_payload` Langfuse-observer privacy knob (symmetric to §5.5.4's `disable_llm_payload`, default ON), the three-lever source decision tree (caller hook → raw state when knob is off → privacy-safe minimal stub), a closed `{completed, failed}` status enum on the stub's `trace.output`, the caller-hook contract for optional domain-shaped summaries, and resume semantics (fresh Langfuse trace per resumed `invocation_id`, hooks re-fire on the resumed trace) by [proposal 0043](../../proposals/0043-observability-langfuse-trace-input-output.md)
  - §4.3 *Parent-child rules* gained a parallel-branches dispatch span rule (inner-branch spans parent under a synthesized per-branch dispatch span); §6 *Driving span lifecycle* span-stack key widens to include `branch_name` and gains a *Parallel-branches dispatch span synthesis* sub-paragraph (cache + key by the parallel-branches NODE's full event-source identity + lazy per-branch dispatch span creation on first inner event); new §5.7 *Parallel-branches span attributes* added — `openarmature.node.branch_name` (new OTel attribute paralleling `openarmature.node.fan_out_index`), `openarmature.parallel_branches.parent_node_name` on dispatch spans, plus `openarmature.parallel_branches.branch_count` and `openarmature.parallel_branches.error_policy` on the parallel-branches node span by [proposal 0044](../../proposals/0044-parallel-branches-dispatch-span.md)
  - §3.4 *Mid-invocation augmentation* ancestor/sibling boundary rewritten as a lineage-aware three-rule structure — *Augmenter's call-stack ancestor chain (MUST)* (each strict dispatch ancestor on the augmenter's specific call-stack path — outer fan-out instance, outer parallel-branches branch, outer serial-subgraph wrapper — gets the update), *Sibling boundary (MUST NOT)* (siblings at any depth do not), *Shared-parent boundary (MUST NOT)* (the fan-out node, parallel-branches node, invocation span — visible to multiple sibling instances — do not), plus a three-step boundary decision tree; §3.4 *Per-async-context scoping* gained a follow-up *Per-depth lineage tracking* paragraph requiring implementations to preserve the dispatch-context lineage as a list (one entry per dispatch depth) rather than a single scalar identifier, so the observer can locate ancestor open spans at augmentation time by [proposal 0045](../../proposals/0045-observability-nested-lineage-augmentation.md)
  - §5.5.3 extended with a new §5.5.3.1 sub-subsection *OA-namespaced cache attributes (stable-only mirror)* defining two new attributes on the LLM provider span: `openarmature.llm.cache_read.input_tokens` (sourced from the §6 `Response.usage.cached_tokens` field, emitted when the field is populated) and optional `openarmature.llm.cache_creation.input_tokens` (sourced from `Response.usage.cache_creation_tokens`, populated primarily by providers with explicit cache-control surfaces); OA-namespace placement governed by the *Stable-only upstream adoption* policy because the upstream OTel attribute names `gen_ai.usage.cache_read.input_tokens` / `gen_ai.usage.cache_creation.input_tokens` are at Development status as of OTel semconv v1.41.1; emission honors the existing `disable_genai_semconv` opt-out (§5.5.4) by [proposal 0047](../../proposals/0047-implicit-prefix-cache-wire-stability.md)
  - §3.4 *Caller-supplied invocation metadata* extended with a *Read access* paragraph block introducing the symmetric `openarmature.observability.get_invocation_metadata()` read primitive — returns an immutable mapping snapshot of the metadata visible in the current async context, scoped per-async-context per the existing copy-on-write rule (sibling-instance writes invisible after fan-out joins; outermost-serial reads see only the outermost view), per-attempt under retry middleware (prior failed attempt's writes do NOT carry over), silent no-op (empty mapping) outside an active invocation, no observer emission on read, immutable-mapping return type with typed wrappers deferred; new §9 *Queryable observer pattern* (renumbers existing §9 *Determinism* → §10 and §10 *Out of scope* → §11) defining a normative convention for concrete observers exposing read methods on the instance — §9.1 read-method contract (query-only, no routing side effects, no observer-side emission, non-blocking SHOULD), §9.2 async-safety contract (read-consistent floor; post-completion stability gates on the invocation's completion signal), §9.3 *Three-channel data-access guidance* table comparing State / invocation-metadata / queryable observer accumulator carve-outs (default: prefer State), §9.4 lifecycle (auto-drop on completion rejected; explicit `drop()` required for accumulating queryable observers; long-lived accumulator memory-pressure caveat) by [proposal 0048](../../proposals/0048-read-symmetric-invocation-metadata-queryable-observer.md)
  - §5.5 gained a new §5.5.7 *Typed LLM completion event* sub-subsection framing the typed `LlmCompletionEvent` variant (defined on the graph-engine §6 observer event union) as the structured form of the §5.5 LLM provider span attribute surface — same identity / scoping / outcome data, in a structured form rather than as separate span attributes; observers MAY filter via type discrimination rather than via the impl-current sentinel-namespace string match; a SHOULD-emit-both transition lets implementations that historically emitted a sentinel-namespaced NodeEvent for LLM completions continue emitting it alongside the typed event for an implementation-defined transition window (the spec does not pin the legacy NodeEvent shape — the sentinel `"openarmature.llm.complete"` value remains the OTel span name per §5 but is impl-current as a NodeEvent's `node_name` value); backends SHOULD subscribe to one variant per LLM completion to avoid double-counting by [proposal 0049](../../proposals/0049-typed-llm-completion-event.md)
  - §5.5 baseline LLM provider span attribute list extended with `openarmature.llm.attempt_index` (int; `0..N-1` for an N-attempt call-level retry per llm-provider §7.1; defaults to `0` when call-level retry is not configured, preserving the single-span case verbatim); §5.5 single-span framing paragraph amended from "MUST emit a span around each `complete()` call" to "one span per attempt under call-level retry; one span per `complete()` call when retry is absent (the default)" — N attempts emit N sibling spans parented under the calling node's span, disambiguated by the new attribute. The attribute is OA-namespace because no upstream OTel GenAI semconv stable equivalent exists; a follow-on proposal MAY mirror to `gen_ai.*` if upstream stabilizes such an attribute by [proposal 0050](../../proposals/0050-retry-and-degradation-primitives.md)
  - §8.4.1 *Trace input/output sourcing* block gained an *Implementation surface caveat* paragraph noting that the vendor SDK method delivering the §8.4.1 contract's UI-visible projection (Langfuse SDK v4's `set_current_trace_io` / `Span.set_trace_io`, empirically verified 2026-05-31) is marked deprecated by the upstream vendor with stated removal in a future major version; the non-deprecated `propagate_attributes` does not currently project to the headline UI columns. The §8.4.1 normative contract (three-lever decision tree, hook signatures, status enum, resume semantics) is explicitly decoupled from any specific SDK-method binding and remains stable across SDK migrations. Cross-references `docs/compatibility.md` per the *External-dependency adoption* policy as the operational tracking record. No conformance fixture impact — the existing §8.4.1 fixture set remains valid unchanged by [proposal 0051](../../proposals/0051-langfuse-trace-io-deprecation-caveat.md)
  - §5.1 invocation span attribute set gained two new implementation-emitted attributes — `openarmature.implementation.name` (string; canonical values `"openarmature-python"` / `"openarmature-typescript"` / `"openarmature-<language>"` matching the language's package-registry shape) and `openarmature.implementation.version` (string; sourced from the implementation library's package metadata in the language-idiomatic way — `openarmature.__version__` for Python, `package.json` `version` for TypeScript). Both attributes are reserved per §3.4 (the reserved-key set extends from 24 → 26 names) so a caller-supplied colliding key is rejected at the `invoke()` API boundary. New *Always-emit invariant* paragraph in §5.1 framing both new attributes plus the existing `spec_version` and `correlation_id` as runtime-identity constants that emit regardless of `disable_state_payload` / `disable_llm_payload` privacy knobs (privacy knobs gate runtime data, not runtime identity). §8.4.1 trace-level mapping table gained two new rows — `openarmature.implementation.name` → `trace.metadata.implementation_name` and `openarmature.implementation.version` → `trace.metadata.implementation_version` — sourced from the §5.1 attributes (parallel to the existing `spec_version` mapping row); the Langfuse rows inherit the always-emit invariant from the §5.1 attributes by [proposal 0052](../../proposals/0052-implementation-attribution-rows.md)
  - §3.4 *Shared-parent boundary (MUST NOT)* paragraph rewritten from "all three are unconditional shared parents regardless of runtime cardinality" prose to a three-bullet structural classification — fan-out node always a shared parent, parallel-branches node always a shared parent, invocation span a shared parent **only when** at least one fan-out or parallel-branches dispatch is on the augmenter's call-stack path (predicate stated via the lineage chain having non-`null` `fan_out_index` or `branch_name` entries; pure-serial augmentations reach the invocation span via rule 2 of the boundary decision tree). The decision tree's rule 3 gains a short parenthetical pointing readers at the conditional invocation-span classification. Documentary tightening only — fixtures 034 (outermost-serial updates invocation span) and 039 (nested cases do not) already exercise the predicate-derived behavior; this proposal closes the spec-text-vs-fixture ambiguity that previously made the two fixtures' behavior unreconcilable from §3.4's text alone by [proposal 0053](../../proposals/0053-shared-parent-boundary-clarification.md)
  - §4.2 *Status mapping* table extended with a new row for the `SUSPENDED` logical status (applied to both the suspending node's span and the invocation root span when a node calls `suspend()` per the suspension capability §3); new *Suspended status mapping* paragraph defining the OTel physical mapping (status `OK` plus an `openarmature.outcome = "suspended"` span attribute, since OTel's native status code field lacks a third state) with backend-mapping freedom for non-OTel backends. §4.3 *Parent-child rules* gained a *Suspended-resume invocation spans* paragraph defining the cross-invocation-span correlation invariant for suspension-resume (per suspension §7) — the resume invocation span carries the same `openarmature.invocation_id` as the suspended one; OTel observers SHOULD additionally link via span-link or parent-of mechanisms; explicitly distinguishes from checkpoint-resume per pipeline-utilities §10.4 (fresh `invocation_id`, correlated only via shared `correlation_id`). New §5.8 *Suspension span attributes* defining `openarmature.suspension.signal_id` (string; always present on a `suspended` node span; carries the descriptor's `signal_id` per suspension §4) and `openarmature.suspension.metadata.*` (flattened descriptor metadata fields, OTel-attribute-compatible scalars per §3.4 value-type contract) with composition rules for detached trace mode (§4.4) by [proposal 0021](../../proposals/0021-graph-suspension.md)
  - §4 *Span hierarchy* gained a new §4.6 *Turn-level wrapper span (harness capability)* — the harness MAY open a turn-level wrapper span around `invoke()` when running inside a deployment runtime, with the invocation root span becoming its child. Wrapper is OPTIONAL (runtimes that already provide a transport-level parent span MAY skip it). Span name + attributes are harness-implementation-defined; turn-level attributes follow §5.6 (`openarmature.session_id` in sessioned mode) and §5.8 (suspension descriptor attributes on signal-resume turns). See the harness capability spec for the full contract by [proposal 0022](../../proposals/0022-harness-contract.md)

This specification is language-agnostic. Each implementation (Python, TypeScript, …) maps its own idioms
onto the behavioral contract described here. Conformance is verified by the fixtures under `conformance/`.

Normative keywords (MUST, MUST NOT, SHOULD, MAY) are used per [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

The observability capability defines two foundational concepts (cross-backend correlation ID,
OpenTelemetry span and log mapping) and two concrete backend mappings — the OTel mapping in §3–§7
and the Langfuse mapping in §8. Future proposals add additional backend mappings as further sibling
sections of this same spec.

---

## 1. Purpose

The observability capability defines normative mappings from OpenArmature's runtime event surface
(graph-engine §6 observer events, specifically the v0.6.0 started/completed event pairs) into
well-known external observability backends. The substrate is provider-neutral; the capability is
where each concrete backend's translation lives.

This spec defines two concrete backend mappings: the **OpenTelemetry** mapping in §3–§7 and the
**Langfuse** mapping in §8. Future proposals add additional backends as further sibling sections
of this same spec; the OTel mapping serves as the reference shape for cross-backend equivalence.

The capability does NOT introduce new graph-engine primitives. It consumes the existing observer
event stream — `started` events open spans, `completed` events close them. An implementation that
emits OTel spans (or Langfuse observations, per §8) is built on top of §6, not into the engine.

## 2. Concepts

**Span.** A unit of work in OTel — a logically distinct interval with a name, start/end timestamps,
status, attributes, and parent-child relationships. The mapping translates each user-meaningful unit
of work in a graph invocation (the invocation itself, each subgraph, each node execution, each fan-
out instance) into a span.

**Span attributes.** Key/value pairs attached to a span. OTel attribute values are restricted to
scalar types (string, int, float, bool) and arrays thereof. The mapping uses dotted-key namespaces
under the prefix `openarmature.`.

**Span status.** OTel spans carry a status of `OK`, `ERROR`, or `UNSET`. The mapping translates
graph-engine §4 error categories into status `ERROR` with a category-bearing description.

**Trace.** OTel's term for a complete tree of spans rooted at a single trace ID. By default, one
outermost graph invocation produces one trace; subgraphs (whether composed via
`add_subgraph_node` or instantiated by a fan-out per pipeline-utilities §9) participate in the
parent invocation's trace as nested spans. Implementations MUST also support an opt-in
**detached** mode for specific subgraphs or fan-outs (§4.4), where the subgraph or fan-out gets
its own trace and the parent's dispatch span carries an OTel `Link` to that new trace.

**Correlation ID.** A per-invocation identifier that flows across observability backends.
Distinct from `invocation_id` — the `invocation_id` (caller-supplied or framework-generated, per
§5.1) correlates spans within a single backend, while `correlation_id` is application-supplied
(or auto-generated when absent)
and is intended to be visible in every backend the implementation emits to. A user running an
LLM workflow with both an OTel backend (system traces, logs) and a Langfuse backend
(LLM-specific traces) uses the `correlation_id` as a join key between them: find a slow request
in Langfuse, search for its `correlation_id` in OTel logs, and see the surrounding
infrastructure activity. See §3 (architectural contract), §5.6 (OTel attribute realization),
and §8.5 (Langfuse attribute realization).

## 3. Cross-backend correlation ID

The **correlation ID** is a per-invocation identifier the framework propagates across every
observability backend the implementation emits to. It is the join key for cross-backend pivots:
when a user has both an OTel backend (system traces, logs) and an LLM-specific backend (e.g.,
Langfuse) configured, the correlation ID lets them follow a single request across both.

This section defines the architectural contract for the correlation ID. The OTel-specific
realization — how it appears on spans and log records — is in §5.6 (cross-cutting attributes)
and §7 (log correlation).

### 3.1 Lifecycle and propagation

The correlation ID is per-invocation and lives for the duration of one outermost `invoke()`
call. Implementations MUST:

- **Accept a caller-supplied ID** at invoke time (e.g., a keyword argument `correlation_id` on
  `invoke()`, an opt-in field on the invocation config record, or equivalent per-language
  convention). When the caller supplies an ID, the framework uses it verbatim.
- **Auto-generate an ID when absent.** When the caller does not supply one, the framework MUST
  generate a UUIDv4 (canonical 36-character form) at the start of the invocation. Caller-
  supplied correlation IDs MAY be any non-empty URL-safe string (the caller might already use
  request IDs from an upstream system, e.g., HTTP `X-Request-Id` headers); the format mandate
  applies only to the auto-generated case so that "you don't supply a correlation ID" produces
  consistent UUIDv4 output across implementations.
- **Propagate via the language's idiomatic context primitive** — Python `ContextVar`,
  TypeScript `AsyncLocalStorage`, equivalents in other languages. The correlation ID MUST be
  readable from anywhere within the invocation's async call tree, including inside nodes,
  middleware, and observers, without explicit threading through function arguments.
- **Reset the context after the invocation completes** so subsequent invocations get fresh
  correlation IDs.

The correlation ID is a string type. Format is implementation-defined beyond "non-empty string,
URL-safe characters." Implementations SHOULD avoid characters that require escaping in OTel
attribute serialization, JSON, or HTTP headers.

### 3.2 Distinction from `invocation_id`

`correlation_id` and `invocation_id` (defined in §5.1) serve different purposes:

| Concept | Generated by | Used for |
|---|---|---|
| `correlation_id` | Caller (or auto-generated when absent) | Cross-backend pivots; users follow a request across separate observability systems |
| `invocation_id` | Caller (or framework-generated when absent) | Within-backend correlation; ties spans of one invocation together inside a single backend |

Both MAY be the same value if the user chooses (e.g., a caller-supplied UUID could be used as
both), but the spec treats them as distinct fields. Backends MUST NOT conflate them.

### 3.3 Backend-mapping contract

Each backend mapping in this spec MUST define how the correlation ID surfaces in that backend.
For the OTel mapping:

- §5.6 specifies the `openarmature.correlation_id` span attribute that MUST appear on every
  span emitted during an invocation.
- §7 specifies the log-record correlation rules — `openarmature.correlation_id` on every log
  record emitted during an invocation, alongside OTel-native `trace_id`/`span_id`.

For the Langfuse mapping, §8.5 specifies how the correlation ID surfaces on Langfuse Trace
and Observation metadata.

Future backend mappings follow the same pattern: each spec section MUST include a "correlation
ID realization" subsection naming the field/attribute/metadata key the backend uses.

**Detached trace mode** (§4.4) does not change correlation ID propagation — the correlation
ID is invocation-scoped, not trace-scoped, so it flows through detached subgraphs and fan-outs
unchanged. A detached subgraph's spans carry the same correlation ID as the parent trace's
spans.

### 3.4 Caller-supplied invocation metadata

In addition to the correlation ID surface (§3.1–§3.3), the framework MUST accept an optional
**caller-supplied metadata mapping** at invoke time. Callers attach a mapping from string keys to
OTel-attribute-compatible values (a `dict[str, AttributeValue]` in Python idiom, where
`AttributeValue` matches OTel's scalar / homogeneous-array type contract; equivalent per
language) carrying arbitrary key/value entries that identify the invocation for search and
filtering in observability backends.

**Lifecycle and propagation.** The mapping is per-invocation and lives for the duration of one
outermost `invoke()` call, alongside the correlation ID. Implementations MUST:

- **Accept the mapping at invoke time** via a per-language idiomatic mechanism (e.g., a
  `metadata` keyword argument on `invoke()`, a field on the invocation-config record,
  equivalent).
- **Propagate via the language's idiomatic context primitive** — Python `ContextVar`,
  TypeScript `AsyncLocalStorage`, equivalents — so the mapping is readable from observers
  without explicit threading through function arguments. Same propagation mechanism as the
  correlation ID (§3.1).
- **Reset the context after the invocation completes** so subsequent invocations get fresh
  metadata.

**Key/value constraints.**

- Keys MUST be strings.
- Values MUST be OpenTelemetry-attribute-compatible scalars: string, int, float (double),
  bool, or homogeneous arrays of those types. Nested objects, null values, and mixed-type
  arrays are NOT permitted (matching OTel's `AttributeValue` type contract — narrower than
  the broader OTLP `AnyValue` container, which permits nested objects and is NOT used here).
- Keys MUST NOT collide with reserved namespaces: `openarmature.*` and `gen_ai.*`.
  Implementations MUST reject (raise an error at the `invoke()` API boundary, before any work
  begins) a metadata mapping that contains a colliding key. The error category is
  implementation-defined per the language's API-boundary error idiom (Python `ValueError`,
  TypeScript `RangeError`, Go error return — same shape as §6 of graph-engine's
  drain-timeout-input validation).
- Caller keys also MUST NOT exactly match any OA-emitted metadata key name that a backend
  mapping in §8 writes at the top level of a backend metadata object (alongside caller-supplied
  keys). These names are reserved so a caller key cannot shadow an OA-emitted field in a backend
  (e.g. Langfuse, §8.4) whose data model places both at the same top level. The current reserved
  set, drawn from the §8.4 Langfuse mapping, is: `correlation_id`, `entry_node`, `spec_version`,
  `detached_child_trace_ids`, `namespace`, `step`, `attempt_index`, `fan_out_index`,
  `subgraph_name`, `fan_out_item_count`, `fan_out_concurrency`, `fan_out_error_policy`,
  `fan_out_parent_node_name`, `prompt_group_name`, `request_extras`, `finish_reason`, `system`,
  `response_model`, `response_id`, `prompt`, `invocation_id`, `branch_name`, `detached`,
  `detached_from_invocation_id`, `implementation_name`, `implementation_version`.
  Implementations MUST reject a caller key that exactly
  matches a reserved name at the `invoke()` API boundary, before any work begins, with the same
  per-language error idiom as the `openarmature.*` / `gen_ai.*` reservation above. The match is
  exact (whole keys, not prefixes), and the reservation applies regardless of which backends are
  wired — these are OA's observability vocabulary, reserved for cross-backend consistency. Any
  future proposal that introduces a new top-level OA-emitted metadata key in a §8 backend mapping
  MUST add the key name to this reserved set.
- Key length, value length, and entry count are NOT constrained by the spec; backends MAY
  enforce their own limits (Langfuse caps trace-metadata values at a vendor-defined size,
  etc.) and surface rejections via existing error channels.

**Invocation-scoped, not trace-scoped.** Detached subgraphs and detached fan-outs (per §4.4)
inherit the metadata from the parent invocation. The mapping is per-invocation context, the
same as `correlation_id`; detached children of the invocation share it.

**Mid-invocation augmentation.** Code executing within a node body, middleware, or observer
MAY add entries to the in-scope metadata mapping during invocation. Implementations MUST
expose a per-language framework helper for this purpose (e.g., a Python
`openarmature.observability.set_invocation_metadata(**entries)` function;
TypeScript equivalent; the spec mandates the behavioral contract, not the exact API name).
The helper:

- Performs an additive merge into the current async context's metadata. Existing keys with
  the same name are overwritten; other keys are preserved.
- Validates added keys against the reserved-key rules above — both the reserved
  `openarmature.*` / `gen_ai.*` namespaces and the reserved OA-emitted metadata key names —
  and the value-type contract above. Violations MUST raise at the call site, before any
  downstream span emission picks up the partially-applied state. The reservation is enforced
  identically at the `invoke()` boundary and at this mid-invocation helper, so a reserved
  name cannot be introduced through either path.
- **Forward flow.** Spans emitted after the call returns carry the additions via normal
  propagation through the async context.
- **Closed spans.** Spans already closed are NOT retroactively updated.
- **Open spans in the augmenting context (MUST).** Spans that are still open at the time of
  the call AND were opened from the augmenting async context (or from an open descendant
  context that shares the mutated mapping copy) MUST be updated in place, where the backend
  SDK supports in-place attribute / metadata update (OTel `set_attribute`; Langfuse
  observation / trace `update`). The *augmenting async context* is the copy-on-write context
  (per the *Per-async-context scoping* paragraph below) in which `set_invocation_metadata`
  executed: for a call in the outermost serial flow the augmenting context's own open spans
  include the invocation span and the calling node's span; for a call inside a fan-out
  instance or parallel branch they include that instance's / branch's dispatch span and any
  inner node span open beneath it (but NOT the shared parent or invocation span — see the
  boundary below). The augmented metadata is thereby visible end-to-end across the spans that
  represent the augmenting work, not only on spans opened afterward.
- **Augmenter's call-stack ancestor chain (MUST).** Spans opened in async contexts that are
  ANCESTORS of the augmenting async context **on the augmenter's specific call-stack path**
  MUST be updated by the augmentation, where the backend SDK supports in-place attribute /
  metadata update. The augmenter's call-stack ancestor chain is the sequence of dispatch-
  context boundaries the augmenter crossed to reach the augmenting context — each outer
  fan-out instance dispatch, each outer parallel-branches branch dispatch, each outer
  serial-subgraph wrapper. Each such ancestor context's open spans (the corresponding
  dispatch / wrapper span and any open node spans within it that share the same call-stack
  path) MUST be updated. For example, a leaf in inner-fan-out instance #0 inside outer-fan-out
  instance #1 has call-stack ancestors outer-instance #1's dispatch span (NOT the shared
  outer fan-out node span, NOT instances #0 / #2); an augmentation at that leaf updates the
  outer-instance #1 dispatch span in addition to the inner-instance dispatch span and the
  leaf's own span.
- **Sibling boundary (MUST NOT).** Spans opened in a SIBLING async context — another fan-out
  instance at any depth, another parallel-branches branch at any depth — MUST NOT be updated
  by the augmentation. The augmentation is per-call-stack-path, not per-fan-out-node and not
  per-invocation: siblings get their own copies of the metadata mapping at dispatch time
  (see *Per-async-context scoping* below), and the augmenter's mutation does not leak across
  the sibling boundary.
- **Shared-parent boundary (MUST NOT).** Spans for a SHARED parent MUST NOT be updated. A
  shared parent is by definition visible to multiple sibling instances / branches; updating it
  would propagate the augmentation to siblings indirectly. Identify a shared parent
  structurally:

  - **Fan-out node span** — always a shared parent. Identified structurally by dispatch-node
    type; the rule applies even in degenerate cases (a fan-out over a single-element list)
    where no sibling instance exists at runtime — the structural classification governs, not
    the live sibling count.
  - **Parallel-branches node span** — always a shared parent. Same structural-classification
    rule; applies even in degenerate cases (a parallel-branches dispatcher with one branch).
  - **Invocation span** — a shared parent **only when at least one fan-out or
    parallel-branches dispatch is on the augmenter's call-stack path**. Concretely: the
    augmenter's lineage chain (per the *Per-depth lineage tracking* paragraph below) contains
    at least one non-`null` `fan_out_index` or `branch_name` entry. When the chain has only
    `null` entries (pure-serial descent — no fork occurred between the invocation entry and
    the augmenter), the invocation span is on the augmenter's call-stack ancestor path and is
    NOT a shared parent; it gets updated per the *Augmenter's call-stack ancestor chain
    (MUST)* rule above.

  The structural framing applies to the fan-out and parallel-branches node spans (whose
  dispatcher nature is intrinsic to their identity); the invocation span's classification is
  conditional on whether any dispatcher has fired on the augmenter's path. Pure-serial
  augmentations (an augmenter inside a node that runs in the outermost serial context, possibly
  nested through serial-subgraph wrappers, with no fan-out or parallel-branches dispatch on the
  call-stack path) reach the invocation span via rule 2 of the decision tree below; nested
  augmentations (inside any fan-out instance or parallel branch) do not reach the invocation
  span because at least one dispatcher is on the path, making the invocation span a shared
  parent.

The boundary decision tree, applied to each open span at augmentation time:

1. Is the span's opening context the augmenting context itself, or a descendant of it that
   shares the mutated mapping copy? → **Update** (the existing same-context rule above).
2. Is the span's opening context on the augmenter's call-stack ancestor path (a strict
   dispatch ancestor on the augmenter's specific path, not a shared parent above the fork)?
   → **Update.**
3. Is the span's opening context a sibling of any context on the augmenter's call-stack
   path, OR a shared parent at any depth (per the conditional invocation-span classification
   in the *Shared-parent boundary* paragraph above)? → **Do not update.**

**Per-async-context scoping.** The metadata mapping is held in the language's idiomatic
async-context primitive (Python `ContextVar`, TypeScript `AsyncLocalStorage`) with
copy-on-write per async context. Fan-out instances (pipeline-utilities §9), parallel-branches
instances (§11), and detached children each receive their own copy at dispatch time;
augmentation calls within one instance MUST NOT leak to sibling instances. This makes the
common fan-out pattern (each instance adds its own per-item identifier — `productId`,
`documentId`, etc. — to its own subtree's spans) work correctly without leakage between
instances. Augmentation within the parent context (before fan-out dispatch, or in code that
runs serially) flows forward to subsequent spans in that context, per normal context-primitive
semantics.

**Per-depth lineage tracking.** The per-async-context copy-on-write rule above is necessary
but not sufficient on its own — the *Augmenter's call-stack ancestor chain (MUST)* boundary
requires implementations to know which dispatch contexts the augmenter has crossed. This
lineage is the chain of outer fan-out instances, outer parallel-branches branches, and outer
serial-subgraph wrappers on the augmenter's specific call-stack path; it is naturally
available to the engine's dispatch machinery, as each `descend_into_fan_out_instance`,
`descend_into_branch`, and `descend_into_subgraph` step pushes a new dispatch boundary onto
the active path. Implementations MUST preserve this lineage as a *list* (one entry per
dispatch depth) — a single scalar identifier (e.g., a lone `fan_out_index` ContextVar that
gets clobbered on each nested descent) is insufficient. When an augmentation fires at a leaf,
the observer uses the lineage to locate the open spans for each ancestor dispatch context on
the augmenter's path (and only those — sibling and shared-parent contexts are not on the
list and therefore not updated).

**Read access.** The framework MUST expose a symmetric read primitive —
`openarmature.observability.get_invocation_metadata()` (per-language idiomatic equivalents follow
the same naming convention as `set_invocation_metadata`). The read returns an **immutable
mapping snapshot** of the metadata visible in the current async context at the time of the call,
carrying string keys and `AttributeValue`-typed values per the existing §3.4 value-type contract.

The read is scoped to the current async context's view of the metadata mapping — i.e., the
context primitive's current value. This includes:

- All entries set via `set_invocation_metadata` in the current async context.
- All entries set via `set_invocation_metadata` in any ancestor context that propagated to the
  current context through dispatch.
- The original caller-supplied metadata mapping from `invoke()`.

Reads do NOT see entries set in sibling async contexts. Per the *Per-async-context scoping*
paragraph above, fan-out instance #0's writes are isolated to instance #0's copy of the mapping
— instance #1's reads do not see them. A node reading at the outermost serial context (e.g.,
after a fan-out joins) sees only the outermost context's view; fan-out instance writes are not
visible after the join. This scoping is the natural consequence of the contextvar's
copy-on-write semantics; implementations MUST NOT layer a separate global aggregator structure
to make sibling-instance writes visible across the join — the read surface mirrors the write
surface's scoping exactly.

**Per-attempt scoping.** Under retry middleware (pipeline-utilities §6.1), each attempt sees
only the metadata set during that attempt plus the ancestor / pre-attempt baseline. Writes from
a prior attempt that subsequently failed do NOT carry over — consistent with
`set_invocation_metadata`'s per-attempt scoping (a per-attempt copy is taken from the
pre-attempt baseline at each retry, and the prior attempt's writes are discarded along with the
attempt itself).

**Outside invocation.** Calling `get_invocation_metadata()` outside an active invocation returns
an empty immutable mapping (silent no-op, mirroring `set_invocation_metadata`'s
silent-no-op-outside-scope behavior). Implementations MUST NOT raise.

**No observer emission.** Reads do NOT emit a metadata-augmentation event (per §6) or any other
observer notification — the augmentation event signals mutations to backends, not consumer
reads.

**Return type.** The read returns an immutable mapping shape (Python `MappingProxyType` or
equivalent; TypeScript `Readonly<Record<string, AttributeValue>>` or equivalent). Typed wrappers
(e.g., a caller-supplied accessor class with strongly-typed field access) are out of scope for
v1; the immutable-snapshot mapping is the spec-normative shape.

**Backend-mapping contract.** The OTel mapping is the primary cross-vendor propagation: §5.6
specifies the `openarmature.user.*` cross-cutting attribute family, which appears on every
span and every OTel log record (§7) emitted during the invocation. Every observability backend
that consumes OTel spans (Phoenix / Arize, Honeycomb, Datadog APM, HyperDX, Grafana Tempo,
custom OTel collectors, etc.) sees the metadata as standard OTel span attributes with no
per-backend wiring beyond the OTel mapping itself.

Backends whose data model carries trace-level metadata as a typed field separate from OTel
span attributes need an additional propagation rule in their respective §-section. The
Langfuse mapping (§8.4.1 + §8.4.2) is the one such backend currently specified; future
observability backend mappings (when proposed) follow the same pattern — they inherit §5.6
cross-cutting attributes by default and only add their own propagation rules if the backend's
data model needs them.

**Cross-backend key portability.** Backends may impose their own constraints on metadata key
names (e.g., Langfuse's propagated metadata limits keys to alphanumeric characters; some
backends disallow dots). Callers who wire OA to multiple observability backends SHOULD use
alphanumeric or camelCase keys (`tenantId`, `userId`, `featureFlag`) for cross-backend
portability. The OA spec's API-boundary validation MUST at least enforce the
reserved-namespace rule above; implementations MAY expand the rejected-key set to also catch
backend-specific constraints early (e.g., a Langfuse-aware implementation rejecting
non-alphanumeric keys at `invoke()` rather than at observer emission). When implementations
do NOT expand, backend-specific key constraints surface at the backend's emission layer.

## 4. Span hierarchy

Each invocation of the outermost graph produces the following span tree:

- **Invocation span.** Root span for the whole call. Spans the time from `invoke()` entering until
  the post-merge state is returned (or an error propagates).
- **Node spans.** One per node execution. Children of the invocation span (for outermost-graph
  nodes) or of a subgraph span (for nodes inside a subgraph) or of a fan-out instance span (for
  nodes inside a fan-out instance — see §4.3).
- **Subgraph spans.** When a `SubgraphNode` runs, a span representing the entire subgraph execution
  wraps the inner-node spans. Child of the parent's invocation or subgraph span; sibling-equivalent
  to the surrounding parent's other node spans.
- **Fan-out spans.** A fan-out node's overall execution is one span (per pipeline-utilities §9);
  each fan-out instance produces its own subgraph span as a child. Per-instance attribution uses
  the `openarmature.node.fan_out_index` attribute (§5.4).
- **Retry attempt spans.** Each retry attempt of a node (per pipeline-utilities §6.1) produces its
  own node span — the v0.6.0 §6 contract dispatches a started/completed pair per attempt, so each
  attempt naturally maps to one span. Per-attempt attribution uses the
  `openarmature.node.attempt_index` attribute (§5.2).

The hierarchy is illustrated for a typical case:

```
invocation (root)
├── node: outer_in
├── subgraph: outer_sub
│   ├── node: inner_x
│   └── node: inner_y
└── node: outer_out
```

### 4.1 Span timing

A node span's start time is the moment the §6 `started` event fires for that attempt. Its end time
is the moment the §6 `completed` event fires for the same attempt. The pair model gives a clean
direct mapping — span open at started, span close at completed — with no middleware bracketing
required.

A subgraph span's start time is the moment the surrounding `SubgraphNode`'s `started` event fires.
Its end time is the moment the same `SubgraphNode`'s `completed` event fires.

The invocation span's start time is the entry of `invoke()`; its end time is the return. The
invocation span is the OTel parent for all top-level node spans within that invocation.

Implementations drive span lifecycle by registering an observer with the default phase
subscription (both `started` and `completed`); the OTel observer maintains a stack of open spans
keyed by `(namespace, attempt_index, fan_out_index, branch_name)` and pairs each `completed`
event with its corresponding `started`. Because the §6 delivery queue is strictly serial across an invocation,
the start/close pairing is unambiguous.

Implementations MAY also use pipeline-utilities middleware as the lifecycle driver if they prefer
— middleware can open the span in its pre-phase and close it in its post-phase. Both approaches
produce identical span structure for conformance purposes; the contract is the emitted spans, not
the driver mechanism. Most implementations will pick the observer-driven path for simplicity.

### 4.2 Status mapping

A span's OTel status is set as follows:

| Outcome | Status | Description |
|---|---|---|
| Node returns successfully and merge succeeds | `OK` | (omit description) |
| Node raises (graph-engine §4 `node_exception`) | `ERROR` | the §4 category identifier |
| Edge function raises (`edge_exception`) | `ERROR` | the §4 category identifier; status applied to the *preceding* node span |
| Reducer raises (`reducer_error`) | `ERROR` | the §4 category identifier |
| Routing error (`routing_error`) | `ERROR` | the §4 category identifier; status applied to the preceding node span |
| State validation error (`state_validation_error`) at entry | `ERROR` | the §4 category identifier; status applied to the invocation span (no node has run yet) |
| State validation error (`state_validation_error`) at a node boundary | `ERROR` | the §4 category identifier; status applied to the failing node's span (per the SHOULD-validate-at-node-boundaries rule in graph-engine §2) |
| State validation error (`state_validation_error`) at exit | `ERROR` | the §4 category identifier; status applied to the invocation span (failure is at the framework boundary, not tied to any node) |
| Node calls `suspend()` per suspension §3 | `SUSPENDED` (logical) | logical status distinct from OK and ERROR; suspension is intentional, not a failure. See *Suspended status mapping* below. Applies to both the suspending node's span and the invocation root span (both close at suspend time per §4.1's *Span timing*). |

When a span is set to `ERROR`, an OTel exception event MUST be recorded on the span carrying the
exception's class name and message; the exception's stack trace SHOULD be attached when the
language's OTel SDK supports it.

**Suspended status mapping.** The logical `SUSPENDED` status above is the spec's third-category
outcome alongside `OK` and `ERROR`. OTel's native status code field has only `UNSET`, `OK`, and
`ERROR` — implementations MUST map the logical `SUSPENDED` to OTel `OK` plus an
`openarmature.outcome = "suspended"` span attribute on both the suspending node's span and the
invocation root span. The suspending node's span additionally carries the suspension-attribute
set per §5.8. Other observability backends MAY use a native suspended status if their data model
supports one (e.g., a Trace status enum on Langfuse-side mappings); the spec defines the logical
status, not the per-backend physical representation.

The three `state_validation_error` rows above attribute the failure to exactly one span — the
specific span where the validation occurred. The invocation span inherits `ERROR` via standard
OTel parent-status-from-failed-children propagation when any of these fail, but the spec does
NOT explicitly mark the invocation span ERROR for the node-boundary case (the inheritance is
sufficient — explicit duplicate attribution would create noise without adding diagnostic value).

### 4.3 Parent-child rules

Spans are parented as follows, using the §6 `namespace`, `fan_out_index`, and `branch_name` fields:

- A node event with `namespace = [name]` and `parent_states = []` corresponds to an outermost-graph
  node. Its span's parent is the invocation span.
- A node event with `namespace = [outer_sub, inner_name]` corresponds to a node inside a subgraph.
  Its span's parent is the subgraph span for `outer_sub`.
- A node event with `namespace = [outer_sub, even_inner_sub, inner_inner_name]` corresponds to a
  node inside a doubly-nested subgraph. Its span's parent is the doubly-nested subgraph span.
- A node event with `fan_out_index` populated corresponds to a node inside a fan-out instance.
  Its span's parent is the fan-out instance span (one per `fan_out_index` value).
- A node event with `branch_name` populated corresponds to a node inside a parallel-branches
  branch. Its span's parent is the per-branch dispatch span (one per `branch_name` value within
  the parallel-branches node's execution) — a span synthesized by the OTel observer between the
  parallel-branches node span and the branch's inner-node spans. See §5.7 for the dispatch span's
  attributes and §6 for the observer synthesis behavior.
- A node event with `attempt_index > 0` corresponds to a retry attempt. Each attempt produces its
  own node span — the spans for attempts 0..N-1 are siblings sharing the same parent (typically
  the invocation span, subgraph span, fan-out instance span, or per-branch dispatch span
  depending on context).

When a node event has BOTH `fan_out_index` AND `branch_name` populated (a node inside a
parallel-branches branch nested in a fan-out instance, or vice versa — graph-engine §6
explicitly allows both), the immediate parent span is the **innermost** containing wrapper
among the per-branch dispatch span and the fan-out instance span — determined by namespace
ancestry depth (each wrapper's namespace position fixes its ancestor depth in the trace tree).
The other span is a higher ancestor in the trace tree, not the immediate parent. The single-
population bullets above describe the common case; this rule handles the mixed-nesting case.

The invariant `len(parent_states) == len(namespace) - 1` from §6 is preserved by this mapping: each
parent-state entry corresponds to exactly one ancestor span. The `attempt_index`, `fan_out_index`,
and `branch_name` fields disambiguate sibling spans at the same hierarchy level.

**Suspended-resume invocation spans.** A suspension-resume invocation (per suspension §7) reuses
the suspended invocation's `invocation_id` from the paused record. The resume opens a new
invocation span carrying the same `invocation_id` value as the suspended invocation span; the
suspend and resume spans are correlated by shared `openarmature.invocation_id` (per §5.1). OTel
observers SHOULD additionally link the resume invocation span to the suspended invocation span
via OTel's span-link mechanism or a parent-of relationship per OTel conventions. Whether the
resume span is a continuation of the suspend span or a sibling under a shared trace is
backend-mapping-dependent; the spec defines the correlation invariant (shared `invocation_id`),
not the per-backend physical representation. This rule applies only to suspension-resume per
suspension §7; checkpoint-resume per pipeline-utilities §10.4 mints a fresh `invocation_id` and
therefore opens an unrelated invocation span (correlated to the original via shared
`correlation_id` per §3.1, not via shared `invocation_id`).

### 4.4 Detached trace mode (opt-in)

The default behavior described in §4.1–§4.3 puts every span produced during a single `invoke()`
call into one trace. This is the right default for typical LLM workloads but breaks down in two
cases: very large fan-outs (thousands of items produce thousands of sibling spans, slowing backend
UIs and complicating filtering) and long-running subgraphs (sampling decisions at the trace root
can drop everything; real-time visibility into intermediate progress is hard while the parent
trace is still open).

For these cases, implementations MUST support a **detached** trace mode, opt-in per subgraph or
per fan-out node. The configuration mechanism is implementation-defined (e.g., a parameter on the
OTel observer's constructor naming detached subgraph and fan-out node names; per-language
ergonomic API). The behavioral contract is what follows, regardless of how the user expresses the
opt-in.

When a subgraph or fan-out is configured as **detached**:

- The implementation creates a new OTel `SpanContext` (new `trace_id`) at the subgraph's or
  fan-out's entry — distinct from the parent's invocation `trace_id`.
- The parent's subgraph-dispatch span (or fan-out node span) is opened in the parent's
  invocation trace as usual, BUT carries an OTel `Link` whose target is the new detached
  `trace_id`. The link associates the parent's record of "this subgraph dispatched" with the
  detached trace's full record of "this is what happened inside" without parent-child semantics.
- All spans inside the detached subgraph or fan-out — node spans, nested subgraph spans, retry
  attempt spans, LLM provider spans — use the new `trace_id` as their root. They are NOT
  children of the parent's invocation span.
- The parent's subgraph-dispatch span ends when the subgraph completes (per §4.1 timing rules)
  and reflects the subgraph's outcome via §4.2 status mapping. Status propagation across the
  trace boundary uses OTel's standard link semantics — the parent's status reflects the
  parent's view of the dispatch outcome.
- For detached **fan-out**: each instance gets its OWN trace (one trace per instance). The
  fan-out node's span carries one Link per instance trace. Detaching at the fan-out level
  effectively turns N concurrent instances into N concurrent traces with N links from the
  fan-out node.

When a subgraph or fan-out is **NOT** configured as detached (the default), §4.1–§4.3 nested
behavior applies — everything in one trace.

**Composition with `attempt_index`.** Retry attempt spans live in the same trace as their parent
node — `trace_isolation` does NOT apply per-attempt; it applies per-subgraph or per-fan-out. A
retried node inside a detached subgraph produces sibling attempt spans inside the detached trace.

**Composition with nested subgraphs.** Detached mode applies at the subgraph or fan-out where it
is configured. A detached subgraph that itself contains a non-detached inner subgraph keeps the
inner subgraph nested within the (now-detached) outer subgraph's trace. A detached subgraph that
contains a detached inner subgraph produces three separate traces (parent, outer detached, inner
detached) with two Links.

**Configuration example** (informative; per-language API):

```
# Python — opt-in via OTel observer constructor
otel_observer = OTelObserver(
    detached_subgraphs={"long_running_workflow"},
    detached_fan_outs={"per_document_scoring"},
)
graph.add_observer(otel_observer)
```

The implementation looks up the relevant set when entering a subgraph or fan-out by name and
creates the detached trace if matched. Other detachment-configuration shapes (decorator,
graph-builder argument, etc.) are equivalently valid as long as the behavioral contract above
holds.

### 4.5 Span names

Span names are how OTel trace UIs identify each span in lists, search results, and aggregations.
Implementations MUST use these names for spans they emit:

| Span type | Span name |
|---|---|
| Invocation span | `"openarmature.invocation"` (constant) |
| Node span | The node's registered name in its containing graph (e.g., `"summarize_doc"`, `"score_relevance"`) |
| Subgraph span (regular `add_subgraph_node`) | The SubgraphNode's name in the parent graph |
| Fan-out node span (the parent dispatch span) | The fan-out node's name in the parent graph |
| Fan-out instance span (each instance's subgraph dispatch) | The fan-out node's name in the parent graph; disambiguated from the fan-out node span and from siblings by the `openarmature.node.fan_out_index` attribute and parent-child hierarchy |
| LLM provider span | `"openarmature.llm.complete"` (constant) |
| Retry attempt spans | Same name as the wrapped node; disambiguated from sibling attempt spans by the `openarmature.node.attempt_index` attribute |

Rationale: trace UIs display span names prominently. User-named spans (node, subgraph, fan-out)
let users find their familiar labels in the UI without indirection — "I see a span called
`summarize_doc`, that's the one I wrote." Framework-emitted spans that are not user-named
(invocation, LLM provider) use a constant `openarmature.*` prefix so they're identifiable as
framework emissions without colliding with user-chosen names. Cardinality concerns are
typically not a problem for LLM workflows (10–50 nodes per pipeline, not thousands); backends
needing low-cardinality aggregations build them from the `openarmature.node.name` attribute
(per §5.2) instead.

### 4.6 Turn-level wrapper span (harness capability)

When an OpenArmature graph runs inside a deployment runtime via a harness (per the harness
capability spec), the harness MAY open a **turn-level wrapper span** around the `invoke()` call.
The invocation root span (per §4.1) becomes a child of the turn span; the trace hierarchy from
root to leaf becomes:

```
turn span  (harness)
└── invocation span  (this spec, §4.1)
    └── node spans
        └── ...
```

The turn span MUST carry whatever turn-level attributes the harness deems useful for trace
correlation (`openarmature.session_id` per §5.6 in sessioned mode; signal descriptor attributes
per §5.8 on signal-resume turns). The span name and additional attributes are harness-
implementation-defined.

This wrapper span is OPTIONAL — harnesses MAY skip it if the runtime already provides a
transport-level parent span (e.g., an OTel-instrumented FastAPI adds a request span; the
invocation span becomes its child directly). The wrapper exists so trace UIs can scope traces to
turns when a runtime-level parent is absent. See the harness capability spec for the contract.

## 5. Attribute namespace

All openarmature-emitted attributes use the prefix `openarmature.`. The mapping defines the
following normative attribute keys; implementations MUST emit each on the spans listed.

### 5.1 Invocation span attributes

- `openarmature.invocation_id` — string. A unique identifier for this invocation.
  **Caller-supplied or framework-generated.** When the caller supplies an id at invoke time, the
  framework uses it verbatim; a caller-supplied id MAY be any non-empty URL-safe string. When the
  caller does not supply one, the framework MUST generate a UUIDv4 (canonical 36-character form:
  `xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`). The UUIDv4 format mandate applies only to the
  framework-generated case, so not supplying an invocation id produces consistent UUIDv4 output
  across implementations (dashboard queries, log searches, and cross-tool correlation assume the
  same shape). Backends that derive a fixed-width identifier from `invocation_id` (e.g., the
  Langfuse `trace.id` per §8.4.1) define their own derivation for non-UUID values.
- `openarmature.graph.entry_node` — string. The entry node name of the outermost graph.
- `openarmature.graph.spec_version` — string. The version of the openarmature-spec the
  implementation targets (e.g., `"0.7.0"`). Sourced from the implementation's package metadata.
- `openarmature.implementation.name` — string. The OA implementation that emitted the
  invocation. Canonical values match each language's package-registry shape:
  `"openarmature-python"` (PyPI), `"openarmature-typescript"` (npm), per-language equivalents
  for future ports under the `openarmature-<language>` convention. Implementation-emitted; never
  caller-supplied (reserved per §3.4). Stable per implementation; never null.
- `openarmature.implementation.version` — string. The OA implementation's release identifier,
  sourced from the implementation library's package metadata in the language-idiomatic way
  (Python: `openarmature.__version__`; TypeScript: `package.json` `version` field; per-language
  idiomatic equivalents otherwise). Implementation-emitted; never caller-supplied (reserved per
  §3.4). Never null. Pre-release tags (e.g., `"0.12.0-rc.1"`) MAY appear; the spec does NOT
  mandate semver vs CalVer vs any specific versioning discipline — the value matches the
  package's release identity in whatever shape the package registers under.

**Always-emit invariant.** `openarmature.implementation.name` and
`openarmature.implementation.version` MUST be emitted on every invocation span regardless of
the `disable_state_payload`, `disable_llm_payload`, or any other observer-level privacy knob.
These attributes describe the OA runtime itself — they are runtime-identity constants, not
runtime data. The privacy-knob framing applies to runtime data (caller state, LLM messages,
etc.), not to runtime identity. The pattern is parallel to `openarmature.graph.spec_version`
(above) and `openarmature.correlation_id` (§3.1 / §5.6) — all four mandated, all four
always-emit, all four implementation-emitted (not caller-supplied). The §8.4.1 Langfuse-mapping
rows derived from these attributes inherit the same always-emit invariant.

Canonical implementation-name values per language follow the package-registry shape so
operators can copy the name directly into the registry's search box without transliteration:

| Implementation | `openarmature.implementation.name` value | `openarmature.implementation.version` source |
|---|---|---|
| openarmature-python | `"openarmature-python"` | `openarmature.__version__` |
| openarmature-typescript | `"openarmature-typescript"` | `package.json` `version` field |
| Future language ports | `"openarmature-<language>"` (matches PyPI / npm / cargo / etc. naming for that ecosystem) | language-idiomatic package-metadata source |

### 5.2 Node span attributes

Required on every node span:

- `openarmature.node.name` — string. The node's name in its immediate containing graph.
- `openarmature.node.namespace` — string array. The §6 `namespace` field, as an OTel string array.
  Implementations MUST NOT join the namespace into a single string at the OTel boundary.
- `openarmature.node.step` — int. The §6 `step` field.

- `openarmature.node.attempt_index` — int. The §6 `attempt_index` field. `0` for nodes not wrapped
  by retry middleware; `0..N-1` across the N spans produced by an N-attempt retry.

When the node fails:

- `openarmature.error.category` — string. The §4 category identifier (e.g., `node_exception`,
  `reducer_error`). Set on the `completed` span only; `started` spans never carry an error
  attribute.

### 5.3 Subgraph span attributes

Required on every subgraph span:

- `openarmature.node.name` — string. The name of the `SubgraphNode` in the parent graph.
- `openarmature.subgraph.name` — string. The compiled subgraph's name (if the implementation tracks
  one) or the empty string. Optional in practice; populated when available.

### 5.4 Fan-out span attributes

The following attributes MUST appear on fan-out instance spans (per pipeline-utilities §9):

- `openarmature.node.fan_out_index` — int. The §6 `fan_out_index` for this instance.
- `openarmature.fan_out.parent_node_name` — string. The fan-out node's name in the parent graph.

Fan-out node spans (the parent of the per-instance subgraph spans) carry:

- `openarmature.fan_out.item_count` — int. The resolved instance count (matches the `count_field`
  value when configured; matches `len(items_field)` in items_field mode).
- `openarmature.fan_out.concurrency` — int. The resolved concurrency bound (or a sentinel int for
  unbounded; `0` is RECOMMENDED).
- `openarmature.fan_out.error_policy` — string. One of `"fail_fast"` or `"collect"`. Useful for
  filtering traces by policy.

Implementations source these attributes from the corresponding graph-engine §6 `NodeEvent`
fields, preserving the two-span-category distinction above:

- **Fan-out node span attributes.** `openarmature.fan_out.item_count`,
  `openarmature.fan_out.concurrency`, and `openarmature.fan_out.error_policy` go on the
  fan-out node span. Sourced from `event.fan_out_config` on the fan-out node's own
  `started`/`completed` events.
- **Fan-out instance span attributes.** `openarmature.fan_out.parent_node_name` goes on the
  per-instance fan-out instance spans (not on the fan-out node span). It is also surfaced via
  `event.fan_out_config` on the fan-out node's `started` event, but per-instance events don't
  themselves carry `fan_out_config` — the observer caches the value from the fan-out node's
  started event and applies it when synthesizing each per-instance instance span.
  `openarmature.node.fan_out_index` also goes on per-instance instance spans (and on
  inner-node spans nested below); it is sourced directly from `event.fan_out_index` on those
  inner-node events.

The per-instance span layout (one per-instance subgraph span as a child of the fan-out node
span, with inner-node spans nested below) is required by §4 for both detached and
non-detached fan-out modes — the only behavioral difference between detached and non-detached
is the trace-id treatment per §4.4, not the per-instance layout.

### 5.5 LLM provider attributes

Implementations of the llm-provider capability (per llm-provider §5 / proposal 0006), when paired
with an OTel observer per this mapping, MUST emit a span per LLM provider attempt: one span per
`complete()` call when call-level retry is not configured (the default — preserving the
existing single-span framing), and one span per attempt when call-level retry per llm-provider
§7.1 produces N attempts. The per-attempt spans are siblings parented
under the calling node's span, disambiguated by the `openarmature.llm.attempt_index` attribute
(per §5.5 below). This is a cross-capability coupling: any implementation that ships both
llm-provider and the OTel mapping MUST wire them together so that LLM calls are not invisible
in the OTel trace. Production observability has no gaps by default rather than hoping the user
remembered to instrument LLM calls. The §6 TracerProvider-isolation requirement prevents this from duplicating spans with
external auto-instrumentation libraries (OpenInference, opentelemetry-instrumentation-openai,
etc.), which write to the OTel global provider while openarmature writes to its private one.

**Opt-out for external-instrumentation-only setups.** Implementations MUST support disabling
the openarmature-emitted LLM provider span — a configuration parameter on the OTel observer
(implementation-defined ergonomics; e.g., `disable_llm_spans=True`). This serves the explicit
case where the user prefers their external auto-instrumentation library as the canonical source
of LLM spans and wants openarmature to stay out of that lane. With the flag enabled, the OTel
observer skips the §5.5 span entirely; all other spans (node, subgraph, fan-out, etc.) continue
to emit normally per their respective rules. See §5.5.4 for the additional payload and GenAI
semconv opt-out flags introduced by proposal 0024.

The LLM provider span's parent is the node span of the node that invoked the provider. This
provides direct attribution of LLM calls to the graph nodes they originate from.

**Baseline attributes (v0.7.0).** The following attributes are emitted on every LLM provider
span unless the span itself is suppressed via `disable_llm_spans`:

- `openarmature.llm.model` — string. The model identifier the provider is bound to.
- `openarmature.llm.finish_reason` — string. The llm-provider §6 `finish_reason` from the response.
- `openarmature.llm.usage.prompt_tokens`, `openarmature.llm.usage.completion_tokens`,
  `openarmature.llm.usage.total_tokens` — int. From the response's usage record. Omit when null.
- `openarmature.llm.attempt_index` — int. The retry-attempt index for the LLM call, where `0`
  is the first attempt and `0..N-1` covers the N spans produced by an N-attempt call-level
  retry per llm-provider §7.1. Emitted on every LLM provider span; defaults to `0` when
  call-level retry is not configured on the `complete()` call (a single attempt produces a
  single span with `attempt_index = 0`). Paralleled with `openarmature.node.attempt_index`
  per §5.2 for node-level retry; the two attributes are independent (a per-call retry attempt
  `0` MAY be nested under a node-level attempt `1`, etc.). The attribute lives in the
  `openarmature.llm.*` namespace per the §5.5.2 framing precedent; if the OpenTelemetry GenAI
  semconv adds a stable `gen_ai.*` equivalent in a future release, a follow-on proposal MAY
  mirror this attribute to both namespaces per the §5.5.3 / §5.5.3.1 mirror pattern.

The remainder of §5.5 extends the attribute set across several sub-subsections: input/output
payload (§5.5.1, default-off), `RuntimeConfig` request parameters under the OpenTelemetry GenAI
semantic conventions (§5.5.2), a minimum set of GenAI semconv response attributes (§5.5.3 — with
OA-namespaced cache attributes in §5.5.3.1 per proposal 0047), the two opt-out flags governing
payload and GenAI semconv emission (§5.5.4), the truncation contract governing payload byte
length (§5.5.5), cross-implementation consistency rules (§5.5.6), and the typed LLM completion
event (§5.5.7, per proposal 0049) framing the same data surface in structured-event form. No
existing attribute is renamed; all additions sit alongside the baseline list.

#### 5.5.1 Input/output payload attributes (default-off)

When the LLM payload-emission flag is enabled (per §5.5.4), implementations MUST emit the
following attributes on the LLM provider span:

- `openarmature.llm.input.messages` — string. The messages list sent to the provider,
  JSON-encoded per the llm-provider §3 message shape. Each message is serialized as
  `{role, content, tool_calls?, tool_call_id?}`. Content blocks (per llm-provider §3.1) are
  serialized with the discriminator (`{type, text}` for text blocks,
  `{type, source, media_type?, detail?}` for image blocks) — but inline image bytes are replaced
  with a placeholder per §5.5.5. The serialization MUST be deterministic for identical inputs
  *within an implementation* — i.e., the same implementation with the same input MUST produce
  identical bytes. Cross-implementation bytewise stability (Python and TypeScript producing
  identical bytes for the same input) is NOT required by this specification — JSON encoding rules
  vary across language standard libraries (number formatting, string escaping, key-ordering
  details), and mandating bytewise equality across implementations would require a canonical
  JSON scheme like RFC 8785 JCS, which is out of scope here. Implementations MUST sort object keys
  lexicographically and MUST emit UTF-8-encoded output without insignificant whitespace; the
  conformance fixtures assert that the attribute parses to an equivalent §3 message structure
  rather than bytewise equality.

- `openarmature.llm.output.content` — string. The assistant's response content verbatim, as
  returned by the provider in the §6 `message.content` field. Emitted only when `message.content`
  is non-empty (assistant messages with only `tool_calls` and empty content MUST NOT emit this
  attribute). When `Response.parsed` is populated (per llm-provider §6, structured output), this
  attribute carries the unparsed `message.content` string, NOT a re-serialization of `parsed` —
  matching the llm-provider §6 rule that `message.content` is verbatim.

- `openarmature.llm.request.extras` — string. The `RuntimeConfig` extras mapping (the
  `extra="allow"` pass-through fields permitted by llm-provider §6), JSON-encoded as an object.
  Emitted only when the mapping is non-empty. This attribute is OA-shape (the extras bag is the
  spec's structure, not the GenAI semconv's); it is grouped with payload because it MAY contain
  provider-specific parameters that warrant the same default-off treatment as messages.
  Implementations MAY choose to gate `request.extras` separately from `input.messages` /
  `output.content`; the default is to gate all three under the same flag.

All three attributes are subject to the §5.5.5 truncation contract.

#### 5.5.2 Request parameters

Implementations MUST emit the following attributes on the LLM provider span when the
corresponding `RuntimeConfig` (§6 of llm-provider) field is set on the request, unless the GenAI
semconv opt-out is enabled (per §5.5.4):

- `gen_ai.request.temperature` — double. Mapped from `RuntimeConfig.temperature`.
- `gen_ai.request.max_tokens` — int. Mapped from `RuntimeConfig.max_tokens`.
- `gen_ai.request.top_p` — double. Mapped from `RuntimeConfig.top_p`.
- `gen_ai.request.seed` — int. Mapped from `RuntimeConfig.seed`.
- `gen_ai.request.frequency_penalty` — double. Mapped from `RuntimeConfig.frequency_penalty`.
- `gen_ai.request.presence_penalty` — double. Mapped from `RuntimeConfig.presence_penalty`.
- `gen_ai.request.stop_sequences` — string array. Mapped from `RuntimeConfig.stop_sequences`.
  Both the OA declared field and the GenAI semconv attribute use the same name; the OpenAI
  request-body field is `stop` (translated by §8.1 of llm-provider). Implementations MUST emit
  the list verbatim, preserving order.

When the corresponding `RuntimeConfig` field is not set (or `RuntimeConfig` is absent on the
call), the implementation MUST NOT emit the attribute. The absence of an attribute means "the
field was not supplied for this call," distinct from "the field was supplied with a zero value."

These attributes use the GenAI semconv namespace directly (no `openarmature.llm.request.*`
parallel). Rationale: `temperature`, `max_tokens`, `top_p`, and `seed` are cross-vendor LLM
parameters with no OpenArmature-specific semantics. The GenAI semconv names for these are settled
in the upstream specification and are the names every LLM-aware OTel backend reads. Adding
OA-prefixed parallels would be pure duplication.

This establishes a precedent that future cross-spec touchpoints follow: **the OpenArmature
attribute namespace is normative for attributes encoding OA-specific state (correlation_id,
prompt identity, error category, fan-out index, etc.); the GenAI semconv namespace is used
directly for cross-vendor LLM parameters and response metadata when the semconv name is stable.**

#### 5.5.3 GenAI semconv response attributes

Implementations MUST emit the following attributes on the LLM provider span unless the GenAI
semconv opt-out is enabled (per §5.5.4):

- `gen_ai.system` — string. The LLM system identifier, per the GenAI semconv enum (`"openai"`,
  `"anthropic"`, `"vllm"`, `"lm_studio"`, etc.). Implementations MUST allow this value to be
  configurable per provider instance. The OpenAI-compatible provider (§8.1 of llm-provider) MUST
  default this value to `"openai"`; callers using the OpenAI-compatible provider with a
  non-OpenAI endpoint (vLLM, LM Studio, llama.cpp server, etc.) MUST be able to override this
  default to the appropriate system identifier. Specific override mechanism (constructor
  argument, factory method, environment variable) is implementation-defined; the behavioral
  contract is that an override is available and effective.

- `gen_ai.request.model` — string. The model the request was made against — the model
  identifier bound to the provider. Mirrors `openarmature.llm.model`; both emit. Rationale: the
  GenAI semconv requires this name for backend recognition; the OA-namespaced version is
  preserved for backwards compatibility with v0.7.0 fixtures.

- `gen_ai.response.model` — string. The model identifier the provider returned in the response
  (the `model` field on the response body, when the provider populates it). Distinct from
  `gen_ai.request.model` because providers MAY return a more specific model identifier than the
  one requested (e.g., requested `gpt-4o`, response carries `gpt-4o-2024-08-06`). Emitted only
  when the provider returns a non-null response model.

- `gen_ai.usage.input_tokens` — int. The prompt token count from the response's usage record.
  Mirrors `openarmature.llm.usage.prompt_tokens`; both emit. Omit when the response's usage
  record is null.

- `gen_ai.usage.output_tokens` — int. The completion token count from the response's usage
  record. Mirrors `openarmature.llm.usage.completion_tokens`; both emit. Omit when null.

- `gen_ai.response.finish_reasons` — string array. The `finish_reason` values from the response,
  as a single-element array (the llm-provider §6 `Response.finish_reason` is a single string; the
  GenAI semconv defines this as an array to accommodate providers returning multiple choices,
  which OA's §6 shape collapses to one). Mirrors `openarmature.llm.finish_reason` as
  string-scalar; both emit, with the GenAI version always wrapped in a one-element array.

- `gen_ai.response.id` — string. The response identifier the provider returned (the `id` field
  on the response body), when present. Useful for cross-referencing OA spans with provider-side
  billing or audit logs. Emitted only when the provider returns a non-null id.

##### 5.5.3.1 OA-namespaced cache attributes (stable-only mirror)

When the llm-provider §6 `Response.usage` cache-stat fields are populated, implementations MUST
emit the following two attributes on the LLM provider span:

- `openarmature.llm.cache_read.input_tokens` — int. Sourced from
  `Response.usage.cached_tokens`. The count of input tokens that hit a prefix cache for this
  call. Emitted only when the `Response.usage.cached_tokens` field is populated (the provider
  reported a cache-read count, including the "reported miss" case of `0`); absent when the §6
  field is absent (the provider did not report cache statistics, e.g., vLLM without
  `--enable-prompt-tokens-details`, or any provider with no implicit-cache reporting).

- `openarmature.llm.cache_creation.input_tokens` — int, optional. Sourced from
  `Response.usage.cache_creation_tokens`. The count of input tokens written to the cache during
  this call. Emitted only when the §6 field is populated; absent otherwise. Populated primarily
  by providers with explicit cache-control surfaces that report a discrete cache-creation count
  alongside the cache-read count; absent for providers that only report implicit cache reads.

Both attributes follow the existing `disable_genai_semconv` opt-out (§5.5.4) — emission is
suppressed when GenAI semconv attributes are suppressed, because the cache attributes are part
of the response-attribute set §5.5.3 governs.

**Stable-only namespace rationale.** The upstream OpenTelemetry GenAI semantic-convention
attributes for these values — `gen_ai.usage.cache_read.input_tokens` and
`gen_ai.usage.cache_creation.input_tokens` — are at **Development** status as of OTel semconv
v1.41.1 (verified 2026-06-01); per the *Stable-only upstream adoption* policy in
`GOVERNANCE.md` (and tracked in `docs/compatibility.md`), OA emits the OA-namespaced parallels
above until the upstream attributes reach **Stable**, at which point a follow-on proposal MAY
add the `gen_ai.*` parallels (or migrate to them outright per the policy's cutover guidance).
Until that happens, OA-aware backends read the `openarmature.llm.cache_*.input_tokens`
attributes; cross-vendor OTel backends will gain `gen_ai.*` attribute support only once the
upstream attributes stabilize.

#### 5.5.4 Opt-out flags

Implementations MUST support the following observer-level configuration flags (specific
ergonomics — constructor argument, builder method, etc. — are implementation-defined; flag names
below are normative for cross-implementation consistency):

- `disable_llm_payload: bool` — default `True`. When `True`, the §5.5.1 payload attributes
  (`input.messages`, `output.content`, `request.extras`) are NOT emitted. When `False`, payload
  attributes emit per §5.5.1, subject to the §5.5.5 truncation contract.

- `disable_genai_semconv: bool` — default `False`. When `True`, the §5.5.2 request-parameter
  attributes and the §5.5.3 response-attribute set are NOT emitted. When `False` (the default),
  GenAI semconv attributes emit per §5.5.2 and §5.5.3.

The existing `disable_llm_spans` flag (above) MUST continue to behave as specified: when `True`,
the LLM provider span is not emitted at all, and none of the attributes specified in §5.5.1
through §5.5.3 are emitted (they have no span to attach to).

The three flags are independent. Typical configurations:

| Configuration | `disable_llm_spans` | `disable_llm_payload` | `disable_genai_semconv` | Outcome |
|---|---|---|---|---|
| Default (out of the box) | `False` | `True` | `False` | LLM span emits with OA + GenAI semconv attributes; no payload. |
| Maximum visibility | `False` | `False` | `False` | LLM span emits with full payload and all attributes. |
| External auto-instrumentation is canonical | `True` | (irrelevant) | (irrelevant) | OA emits no LLM span; external library handles it. |
| OA span without GenAI semconv | `False` | `True` | `True` | OA-namespaced attributes only; useful when an external library is the canonical GenAI emitter and OA's role is internal-only attribution. |

#### 5.5.5 Truncation contract

The §5.5.1 payload attributes (`openarmature.llm.input.messages`,
`openarmature.llm.output.content`, `openarmature.llm.request.extras`) MAY be arbitrarily large in
principle (a long conversation, a verbose model response, a multi-image user message). Emission
without bounds would produce spans larger than typical OTLP exporters accept and inflate
observability storage unbounded. The following contract applies:

**Per-attribute byte cap.** Implementations MUST enforce a maximum byte length on each of the
three payload attributes individually. The default cap is **65,536 bytes (64 KiB)** per
attribute. Implementations MUST allow the cap to be configured per observer (specific mechanism —
constructor argument, environment variable, etc. — is implementation-defined). The byte length
is measured on the UTF-8 encoding of the final attribute string, after JSON serialization and
after inline-image redaction (below).

**Truncation algorithm.** When an attribute's serialized value exceeds the configured cap, the
implementation:

1. Computes M, the pre-truncation byte length of the serialized value.
2. Formats the truncation marker with M substituted:

   ```
   …[truncated, M bytes total]
   ```

   and computes `L_marker`, the UTF-8 byte length of the marker string.
3. Computes the target prefix size `N = configured_cap - L_marker`.
4. Finds `N'` = the largest UTF-8 code-point boundary `≤ N` in the serialized value. If `N`
   falls inside a multi-byte sequence, the implementation MUST backtrack to the previous
   code-point boundary; this prevents splitting multi-byte sequences (CJK, emoji, combining
   marks) and emitting invalid UTF-8 that OTLP exporters may reject.
5. Emits the first `N'` bytes of the serialized value followed by the marker.

The resulting attribute is at most `configured_cap` bytes (may be strictly less if `N' < N` due
to boundary backtracking). The marker is a fixed UTF-8 string (its leading character is U+2026
HORIZONTAL ELLIPSIS, encoded as the 3-byte sequence `0xE2 0x80 0xA6`). It introduces no further
UTF-8 boundary concerns beyond those step 4 already handled, because the implementation appends
the marker as a whole unit — never partially. The marker is appended **outside** any JSON
encoding — the result of truncating a JSON-encoded attribute is not itself parseable JSON, which
is the signal to backend code that the value was truncated. Backends performing custom parsing
get a clean affordance to detect truncation without needing a separate flag attribute.

**Minimum cap.** Implementations MUST reject cap configurations smaller than **256 bytes** at
observer construction time. Rationale: 256 bytes leaves room for the worst-case marker (~36
bytes) plus a diagnostically useful payload preview; caps below this would produce attributes
that are almost entirely marker with little or no preview value. The 256-byte minimum is
normative for cross-implementation consistency.

**Inline-image redaction.** Image content blocks (per llm-provider §3.1.2) carry either a URL
source or inline base64 bytes (per §3.1.3). The URL form is a short string and passes through
unchanged. The inline form is potentially very large (base64-encoded image bytes). When
serializing messages for `openarmature.llm.input.messages`, implementations MUST replace
inline-image source records with a redacted placeholder before JSON encoding:

```
{"type": "image", "source": {"type": "inline_redacted", "byte_count": <N>}, "media_type": <mt>}
```

where `<mt>` is the original `media_type` (preserved at the image-block level per llm-provider
§3.1.2) and `<N>` is the byte length of the original base64-encoded data. The image block's
`detail` field (if present per §3.1.2) is preserved unchanged; only the `source` is replaced
with the redacted variant. The placeholder preserves enough metadata for a reader to understand
"an inline image of this type and approximate size was present" without inlining the bytes
themselves. Implementations MUST NOT emit inline image bytes on the span under any
configuration; this is a hard rule, not gated by `disable_llm_payload` or by the per-attribute
cap.

URL-form images are NOT redacted — the URL is a short string and is informative for trace
readers (it points to the actual image asset). The redaction rule applies only to
`source.type == "inline"`.

**Tool-call serialization.** Assistant `tool_calls` (per llm-provider §3) in
`openarmature.llm.input.messages` are JSON-encoded as `[{"id", "name", "arguments"}, ...]` with
`arguments` serialized verbatim from the parsed mapping. Tool-call argument content is subject
only to the overall per-attribute byte cap; this specification does not specify a separate
per-tool-call cap. (First-class tool-call observability is a separate forthcoming proposal.)

#### 5.5.6 Cross-implementation consistency

Implementations of §5.5.1 through §5.5.5 across languages (Python, TypeScript) MUST agree on:

- Attribute names (exactly as specified above; case- and prefix-sensitive).
- Attribute value types (string, int, double, string-array as specified).
- JSON serialization shape for `input.messages` and `request.extras` — sorted object keys
  lexicographically, UTF-8 encoding, no insignificant whitespace, within-implementation
  determinism per §5.5.1. Cross-implementation bytewise stability is NOT required by this
  specification; a follow-on MAY adopt a canonical JSON scheme (e.g., RFC 8785 JCS) to tighten
  this if cross-impl bytewise equality becomes load-bearing.
- The truncation marker string (`…[truncated, M bytes total]`, including the Unicode ellipsis
  character `…` U+2026, the brackets, the comma, the literal word "truncated", and the integer
  M).
- The inline-image placeholder shape (the
  `{type: "image", source: {type: "inline_redacted", byte_count}, media_type, detail?}` record —
  `media_type` at the image-block level per llm-provider §3.1.2, with `detail` preserved
  verbatim when present).
- The default values: `disable_llm_payload = True`, `disable_genai_semconv = False`,
  `disable_llm_spans = False`.

Per-language ergonomics (constructor argument naming, builder patterns, environment-variable
lookup) MAY differ. The above are the cross-impl behavioral surface.

#### 5.5.7 Typed LLM completion event

Implementations MUST emit the `LlmCompletionEvent` typed variant (per graph-engine §6) on every
LLM call completion that produces a structured response. The typed event carries the same
identity / scoping / outcome data the §5.5 span attribute surface exposes — the §5.5.3 GenAI
semconv response attributes (`gen_ai.system`, `gen_ai.request.model`, `gen_ai.response.model`,
`gen_ai.response.id`, `gen_ai.usage.*`, `gen_ai.response.finish_reasons`), the §5.5.1 payload
attributes (`openarmature.llm.input.messages`, `openarmature.llm.output.content`,
`openarmature.llm.request.extras`), the §5.5.2 GenAI request-parameter family
(`gen_ai.request.temperature`, `gen_ai.request.max_tokens`, etc.), the prompt-identity attribute
family per prompt-management §12 / §8.4.4 (`openarmature.prompt.name`,
`openarmature.prompt.version`, `openarmature.prompt.label`, `openarmature.prompt.template_hash`,
`openarmature.prompt.rendered_hash`, `openarmature.prompt.group_name`), plus the OA-namespaced
cross-cutting attributes (`openarmature.invocation_id`, `openarmature.node.name`, etc.) — in a
structured form
rather than as separate span attributes.

The §5.5.4 `disable_llm_payload` opt-out flag continues to gate rendering of payload-bearing data
(`openarmature.llm.input.messages`, `openarmature.llm.output.content`,
`openarmature.llm.request.extras`) at the OTel observer's rendering boundary. The equivalent
typed-event fields (`input_messages`, `output_content`, `request_extras`) are populated by the
implementation unconditionally; observers respect their own `disable_llm_payload` flag on the
typed-event rendering path identically to the span attribute path.

Observers consuming the typed event for backend-specific rendering (Langfuse generation per
§8.7, OTel span enrichment per §5.5, custom queryable observer accumulators per §9) MAY filter
the observer event stream via type discrimination (`isinstance(event, LlmCompletionEvent)` or
per-language idiomatic equivalent) rather than via the sentinel-namespace string match the
existing convention uses.

**Backwards compatibility with the sentinel-namespace convention.** Some implementations have
historically emitted a sentinel-namespaced `NodeEvent` to drive LLM-call observability — a
common convention rather than a spec-defined shape (e.g., emitting NodeEvents with
`node_name = "openarmature.llm.complete"` so backends can filter by namespace string; the same
value appears in §5 *Span names* as the OTel **span name** for the LLM provider span, but the
spec does NOT pin a NodeEvent shape with that `node_name`). The convention is
implementation-current, not spec-normative; this proposal does not define the legacy event's
shape.

Implementations that have historically emitted such a sentinel-namespaced NodeEvent for LLM
completions SHOULD continue emitting it alongside the new typed `LlmCompletionEvent` during a
transition period — long enough for backends filtering by the impl-current sentinel namespace
to migrate to type-discrimination filtering. The transition period is implementation-defined;
the spec imposes no fixed window. Implementations that have never emitted a
sentinel-namespaced NodeEvent for LLM completions only need to emit the new typed event.

**Backends SHOULD subscribe to one event variant per LLM completion.** When an implementation
emits both the typed event and a sentinel-namespaced NodeEvent for the same LLM call, a backend
filtering for both will receive two distinct events for the same logical completion —
accumulators counting events will double-count, span emitters will double-emit. Backends opting
into the typed event SHOULD stop subscribing to the sentinel NodeEvent for LLM completions; the
two-variant emission is for impl-level transition consumption, not parallel consumption by the
same backend.

**Typed LLM failure event.** Implementations MUST emit the `LlmFailedEvent` typed variant (per
graph-engine §6) on every LLM call failure that raises one of the llm-provider §7 error
categories. The typed event carries the same identity / scoping / request-side field surface
`LlmCompletionEvent` carries, plus the failure-specific `error_category` / `error_type` /
`error_message` fields sourced from the raised exception. Response-side fields (`response_id`,
`response_model`, `usage`, `output_content`, `finish_reason`) are absent from the failure variant
— no response was received.

Observers consuming the typed event for backend-specific rendering (Langfuse generation error per
§8.7, OTel span error status per §5.5, custom queryable observer accumulators per §9) MAY filter
via type discrimination (`isinstance(event, LlmFailedEvent)` or per-language idiomatic equivalent).
The success and failure variants are mutually exclusive on a given LLM call; observers needing
both outcome sides handle them as two separate type-discrimination branches.

With both `LlmCompletionEvent` and `LlmFailedEvent` defined, the impl-current sentinel-namespace
`NodeEvent` convention for LLM observability can retire fully — success and failure paths both
have spec-normative typed equivalents. The SHOULD-emit-both transition window's purpose is met
across both outcome sides; implementations MAY conclude the transition once their backends filter
both typed variants via type discrimination.

### 5.6 Cross-cutting attributes

These attributes appear on EVERY span emitted during an invocation, regardless of span type
(invocation, node, subgraph, fan-out instance, LLM provider call, retry attempt):

- `openarmature.correlation_id` — string. The correlation ID for this invocation, per §3. Set
  on every span when a correlation ID is in scope (which, per §3.1, is the entire duration of
  an invocation — so every span emitted during the invocation MUST carry it). The same
  correlation ID appears on spans within detached subgraphs and detached fan-out instances
  (per §4.4 detached mode).
- `openarmature.session_id` — string. The session id for this invocation, per the sessions
  capability spec. Set on every span emitted during a session-bound invocation — i.e., when
  the caller supplied a `session_id` at `invoke()`. Like `correlation_id`, it propagates
  through the ambient invocation context (sessions §3) and appears uniformly on spans within
  detached subgraphs and detached fan-out instances (per §4.4 detached mode). Absent when the
  invocation is not session-bound.
- `openarmature.user.<key>` — for each entry `(key, value)` in the caller-supplied invocation
  metadata IN SCOPE at the time the span is emitted (per §3.4, where "in scope" reflects
  both the initial mapping supplied at `invoke()` AND any subsequent mid-invocation
  augmentations applied in the current async context), the implementation MUST emit a span
  attribute named `openarmature.user.<key>` with the supplied `value`. The cross-cutting
  scope matches `openarmature.correlation_id`: every span emitted during the invocation
  carries the in-scope set — the invocation span, every node span, every subgraph span,
  every fan-out instance span, every LLM provider span, and every retry attempt span.
  Detached subgraphs and detached fan-out instances (§4.4) also carry the in-scope set, since
  the metadata is invocation-scoped, not trace-scoped. Value types match §3.4 (OTel-attribute
  scalars or homogeneous arrays). Implementations SHOULD update already-open spans (the
  invocation span, ancestor node spans) with later-added entries where the OTel SDK supports
  it, so the augmented metadata is visible on those spans at trace export time.

The `openarmature.user.` namespace is reserved for caller-supplied metadata per §3.4; the OA
spec does NOT define any normative attribute names under this prefix. Future OA-normative
attributes go under `openarmature.*` (the existing namespace) or `gen_ai.*` (when the GenAI
semconv has settled a cross-vendor name). Reserving the `openarmature.user.` prefix gives
callers a stable, collision-free namespace they can rely on across spec versions.

The cross-cutting nature of `openarmature.correlation_id`, `openarmature.session_id`, and
`openarmature.user.*` means observability backends can filter for "all spans related to
request X", "all spans for session Y", or "all spans for tenant Z" with a single attribute
query, regardless of which node, subgraph, or fan-out instance emitted the span.

### 5.7 Parallel-branches span attributes

The following attributes MUST appear on per-branch dispatch spans (synthesized by the OTel
observer per §4.3 and §6):

- `openarmature.node.branch_name` — string. The branch's identifier, sourced from the §6
  NodeEvent `branch_name` field. Also appears on every inner-node span beneath the per-branch
  dispatch span — consistent with how `openarmature.node.fan_out_index` propagates onto inner
  nodes from §5.4. (Newly introduced by proposal 0044; prior spec versions did not define an
  OTel span attribute carrying `branch_name`.)
- `openarmature.parallel_branches.parent_node_name` — string. The parallel-branches NODE's name
  in the parent graph, cached by the observer from the parallel-branches NODE's `started`
  event.

Parallel-branches node spans (the parent of the per-branch dispatch spans) carry:

- `openarmature.parallel_branches.branch_count` — int. The number of branches dispatched.
- `openarmature.parallel_branches.error_policy` — string. One of `"fail_fast"` or `"collect"`
  (per pipeline-utilities §11.5). Useful for filtering traces by policy.

Implementations source these attributes from the corresponding graph-engine §6 NodeEvent
fields, preserving the two-span-category distinction above:

- **Parallel-branches node span attributes.** `openarmature.parallel_branches.branch_count` and
  `openarmature.parallel_branches.error_policy` go on the parallel-branches node span. Sourced
  from `event.parallel_branches_config` on the parallel-branches node's own `started` /
  `completed` events.
- **Per-branch dispatch span attributes.** `openarmature.node.branch_name` and
  `openarmature.parallel_branches.parent_node_name` go on the synthesized per-branch dispatch
  span. The observer caches the `parent_node_name` from the parallel-branches node's `started`
  event (via `parallel_branches_config.parent_node_name`) and applies it on each synthesized
  dispatch span. The branch's `branch_name` is sourced from the first inner event of that
  branch (`event.branch_name`).

**Per-branch dispatch span name.** The OTel observer MUST set the per-branch dispatch span's
`name` attribute to the branch's `branch_name` value (e.g., `"fraud_check"`, `"policy_audit"`).
This matches the Langfuse mapping's per-branch Span observation naming and gives operators a
directly meaningful span name in the trace tree.

### 5.8 Suspension span attributes

When a node calls `suspend()` per the suspension capability §3, the suspending node's span
carries the signal descriptor as the following span attributes:

- `openarmature.suspension.signal_id` — string. The descriptor's `signal_id` (per suspension §4),
  the caller-supplied correlation token for the awaited signal. Always present on a `suspended`
  node span.
- `openarmature.suspension.metadata.*` — flattened descriptor metadata fields. Applications using
  a typed metadata schema (Pydantic / zod / equivalent) MUST have the implementation's
  serializer surface each model field as an individual span attribute under this prefix (e.g., a
  metadata model with fields `kind`, `approver_pool`, `expected_at` produces
  `openarmature.suspension.metadata.kind`, `openarmature.suspension.metadata.approver_pool`,
  `openarmature.suspension.metadata.expected_at`). Each flattened value MUST be an OTel-
  attribute-compatible scalar per §3.4's value-type contract (string, int, float, bool, or
  homogeneous array of those types). Implementations MAY drop or stringify nested objects that
  do not flatten cleanly; the exact policy is implementation-defined and SHOULD be documented.

These attributes apply to the **suspending node's span** specifically. The invocation root span
does NOT carry them (the invocation as a whole is suspended; the descriptor identifies what the
specific suspending node is waiting for, which is node-level attribution). The invocation root
span carries the logical `SUSPENDED` status per §4.2 *Suspended status mapping*; that status
plus the suspending node's `openarmature.suspension.*` attributes together describe the
suspension.

Composition with the §4.4 *Detached trace mode* — a node inside a detached subgraph or detached
fan-out instance that calls `suspend()` records the suspension attributes on its own (detached-
trace) node span per the rules above; the parent trace's invocation span carries the logical
`SUSPENDED` status independently. Cross-trace correlation falls out of the existing detached-mode
attribute set (`detached_from_invocation_id` per §3.4 / §8.4.x).

## 6. Driving span lifecycle

The v0.6.0 §6 pair model gives OTel a natural lifecycle driver: register an observer with the
default phase subscription (both `started` and `completed`), and let the `started` event open the
span and the `completed` event close it.

**Observer-driven (RECOMMENDED).** An OTel observer maintains a stack of in-flight spans keyed by
the §6 event-source identity tuple `(namespace, attempt_index, fan_out_index, branch_name)`. On a
`started` event, it opens a new span with the attributes from §4 and pushes it onto the stack. On
the `completed` event with the matching key, it pops the span, sets the status (per §4.2) and any
error attributes, then closes the span. (`branch_name` is included in the key to disambiguate
inner spans across concurrent parallel-branches branches that share a node name; it is `None` on
events from nodes outside any parallel-branches branch.)

```
async def otel_observer(event):
    key = (tuple(event.namespace), event.attempt_index, event.fan_out_index, event.branch_name)
    if event.phase == "started":
        span = tracer.start_span(span_name(event), attributes=base_attrs(event))
        spans[key] = span
    else:  # completed
        span = spans.pop(key)
        if event.error is not None:
            span.set_status(ERROR, description=event.error.category)
            span.record_exception(event.error.exception)
        else:
            span.set_status(OK)
        span.end()
```

**Parallel-branches dispatch span synthesis.** On a parallel-branches node's `started` event, the
OTel observer:

1. Opens the parallel-branches NODE span (per the observer-driven model above) and attaches the
   §5.7 node-level attributes from `parallel_branches_config`.
2. Caches the resolved `parallel_branches_config` (carrying `parent_node_name` for the
   dispatch-span attribute and `branch_names` for step 5's close ordering) under the
   parallel-branches NODE's full §6 event-source identity
   `(namespace, attempt_index, fan_out_index, branch_name)`. The NODE's `branch_name` is null
   when the NODE itself runs outside any parallel-branches branch (the common case — the NODE
   is the dispatcher, not a node inside a branch); it is non-null when the NODE executes inside
   an outer parallel-branches branch (nested parallel-branches), where per §6 the NODE's event
   carries the outer branch's `branch_name`. Including `branch_name` in the cache key
   disambiguates such nested executions; `attempt_index` and `fan_out_index` similarly
   disambiguate retried attempts and fan-out-instance contexts.

On the **first inner `started` event** received whose containing parallel-branches NODE matches
a cached entry (matched by the inner event's `attempt_index` and `fan_out_index` — which
propagate from the parallel-branches NODE per §6's nested-retry / nested-fan-out rules — and a
namespace prefix that matches the cached NODE's namespace), and whose `branch_name` value
hasn't yet been seen for that cached entry, the observer:

3. Synthesizes a per-branch dispatch span as a child of the parallel-branches NODE span,
   attaches the §5.7 dispatch-span attributes (`branch_name`, `parent_node_name` from the
   cache), and pushes it onto the span-stack keyed by the parallel-branches NODE's full
   event-source identity plus the branch:
   `(parallel_branches_node_namespace, parallel_branches_node_attempt_index,
   parallel_branches_node_fan_out_index, branch_name)`. The dispatch span's start time is the
   moment the inner `started` event fires.
4. The inner event itself opens its span as a child of the synthesized per-branch dispatch span
   (not a direct child of the parallel-branches NODE span).

On the parallel-branches NODE's `completed` event, the observer:

5. Looks up the cache entry by the completing parallel-branches NODE's full §6 event-source
   identity `(namespace, attempt_index, fan_out_index, branch_name)`, then closes the
   per-branch dispatch spans associated with that cache entry in declaration order per the
   cached `parallel_branches_config.branch_names`. Dispatch spans associated with other NODE
   executions (other fan-out instances, other retry attempts, other outer-branch contexts)
   remain open until their respective NODEs' `completed` events fire. Each dispatch span's
   end-time is the moment the parallel-branches NODE's `completed` event fires.
6. Closes the parallel-branches NODE span itself (children-before-parents — this is the
   standard close order for nested-span emission).

The synthesis is **lazy**: the dispatch span is created on the first inner event for each
branch, not eagerly at the parallel-branches NODE's `started`. This keeps the synthesis
observable from existing NodeEvents without requiring the engine to emit per-branch lifecycle
events.

Because the §6 delivery queue is strictly serial across an invocation, the start/close pairing is
unambiguous — `started` and `completed` events for the same attempt are delivered in order, with
no interleaving. The observer's `spans` dictionary never has a key collision during normal
execution.

**Middleware-driven (alternative).** Implementations MAY use a pipeline-utilities middleware as the
lifecycle driver instead:

```
async def otel_middleware(state, next):
    with tracer.start_as_current_span(span_name_for_node()) as span:
        try:
            partial_update = await next(state)
            span.set_status(OK)
            return partial_update
        except Exception as exc:
            span.set_status(ERROR, description=getattr(exc, "category", "unknown"))
            span.record_exception(exc)
            raise
```

Both approaches produce identical span structure for conformance purposes; the contract is the
emitted spans, not the driver mechanism. Most implementations should pick observer-driven for
simplicity (one registration, no per-node opt-in required).

**OpenTelemetry context propagation.** Implementations using the observer-driven path MUST
manually maintain the OTel current-span context — observers run on the §6 delivery queue, not in
the node's call stack, so the OTel SDK's automatic context propagation may not see the right
parent. Implementations using the middleware-driven path get OTel context propagation for free
(the middleware runs in the node's call stack).

**TracerProvider isolation (MUST).** Implementations MUST use a **private** `TracerProvider` for
openarmature-emitted spans. They MUST NOT register this provider as the OTel global
(`trace.set_tracer_provider()` in Python; equivalent global-registration calls in other
languages). Rationale: many other libraries (vendor-neutral OTel auto-instrumentation packages
such as `opentelemetry-instrumentation-openai`, OpenInference, LiteLLM-with-OTel, Langfuse v3, etc.)
emit OTel spans through the global provider when one is set. If openarmature also registered
itself globally, those libraries would emit duplicate spans alongside openarmature's, producing
two spans per LLM call (or per HTTP call, etc.) with different attribute namespaces. The user
sees inflated traces and gets billed/charged for the duplication.

Private-provider isolation lets openarmature emit its spans cleanly without interfering with
whatever other instrumentation the user has configured. The user's separate auto-instrumentation
continues to write to the global provider; openarmature writes to its private provider; both
sets of spans flow to the configured exporter (typically the same OTLP endpoint), and the user
filters or correlates them by attribute namespace.

This pattern is non-obvious but production-validated — naive implementations register globally
and discover the duplication only after deploying. Mandating it in the spec saves every
implementation from rediscovering the issue.

**Reflecting mid-invocation metadata augmentation on open spans.** §3.4 requires (MUST) that open
spans in the augmenting async context pick up entries added mid-invocation by
`set_invocation_metadata`. For the observer-driven lifecycle (the RECOMMENDED driver above) this needs
a notification path: observers run on the §6 serial delivery queue, not in the node body's call stack,
so they do not observe the `set_invocation_metadata` call directly and cannot read the node context's
mapping copy.

The RECOMMENDED mechanism is a framework-emitted **metadata-augmentation event** enqueued onto the same
strictly-serial observer delivery queue that carries node-boundary `started` / `completed` events
(graph-engine §6). The event carries the added `(key, value)` entries (post-validation) plus the
originating lineage identity — `namespace`, `attempt_index`, `fan_out_index`, `branch_name` —
sufficient for an observer to scope the update to the augmenting async context's own open spans.
Routing the augmentation through the serial queue (rather than mutating observer state directly from
the node-body task) preserves the strict-serial invariant the lifecycle driver relies on; ordering
follows naturally — augmentation happens inside a node body, so the event is delivered after that
node's `started` event (the inner span is open) and before its `completed` event (the inner span has
not yet closed), so the target spans are open when the event arrives.

On a metadata-augmentation event, an observer maintaining the in-flight span stack updates, in place,
every open span whose lineage is within the augmenting context's subtree (its dispatch span and any
open inner-node spans beneath it), applying the added entries as span attributes (OTel) / observation
and trace metadata (Langfuse). It MUST NOT touch open spans in ancestor or sibling lineages (§3.4).
Observers that do not maintain metadata-sensitive spans ignore the event.

As with the `started` / `completed` lifecycle, implementations MAY use a different mechanism (e.g., a
middleware-driven driver that reads the live context when it closes each span, or a backend SDK's own
context-update hook) provided the resulting spans satisfy §3.4's open-span-update contract. The
contract is the emitted spans, not the driver mechanism.

## 7. Log correlation

OpenTelemetry has a first-class **Logs** signal alongside Traces and Metrics. Log records carry
their own attributes plus the active OTel `TraceContext` (`trace_id`, `span_id`, `trace_flags`).
Implementations of this OTel mapping MUST integrate the framework's logging output into the
OTel Logs SDK so that:

1. Log records emitted from anywhere within an invocation (framework code, node functions,
   middleware, observers) carry the active span's `trace_id` and `span_id`. This is OTel's
   native trace-log correlation; it falls out of using the OTel Logs SDK when the active
   span context is propagated correctly.
2. Log records carry `openarmature.correlation_id` matching the invocation's correlation ID
   (per §3). This enables cross-backend correlation: a user reading OTel logs in HyperDX,
   Datadog, or another OTel-aware backend can find logs matching a `correlation_id` returned
   from a Langfuse trace or any other backend.

**Required log-record fields:**

- `openarmature.correlation_id` — string. The invocation's correlation ID. Set on every log
  record emitted during the invocation.
- `openarmature.session_id` — string. The session id for this invocation, per the sessions
  capability spec. Set on every log record emitted during a session-bound invocation (i.e.,
  when the caller supplied a `session_id` at `invoke()`). Read from the ambient invocation
  context via the same OTel Logs Bridge mechanism used for `correlation_id`. Absent when the
  invocation is not session-bound.
- `openarmature.user.<key>` — for each entry in the caller-supplied invocation metadata (per
  §3.4), the implementation MUST emit a log-record attribute named `openarmature.user.<key>`
  with the supplied value, on every log record emitted during the invocation. Same OTel Logs
  Bridge mechanism as the `correlation_id` propagation below. Same value-type contract as the
  §5.6 cross-cutting span-attribute family.
- `trace_id`, `span_id` — string. The active span's identifiers, populated automatically by
  the OTel Logs SDK when the user's logger is bridged to OTel Logs (see implementation guidance
  below).

**Implementation guidance** (informative; per-language ergonomics):

- **Python.** Use `opentelemetry-sdk._logs.LoggingHandler` attached to the stdlib `logging`
  root logger. The handler reads the active span context and attaches `trace_id`/`span_id`
  automatically. Inject `correlation_id` via a logging filter that reads the `ContextVar`
  carrying the correlation ID, or via `structlog.contextvars.bind_contextvars` if the user is
  using structlog.
- **TypeScript.** Use the equivalent OTel Logs Bridge for the user's logger (winston, pino,
  bunyan all have OTel bridges). Inject `correlation_id` via the bridge's context-attribute
  mechanism reading from `AsyncLocalStorage`.

**Detached trace mode (§4.4) and log correlation.** Log records emitted inside a detached
subgraph or fan-out instance carry the *detached* trace's `trace_id` and `span_id`, NOT the
parent invocation's. The `correlation_id` is unchanged (invocation-scoped, not trace-scoped).
This means filtering logs by `correlation_id` finds all logs across all detached and parent
traces; filtering by `trace_id` finds only the logs from one specific trace. When the
invocation is session-bound, `openarmature.session_id` is also invocation-scoped and is
unchanged across detached and parent traces, behaving identically to `correlation_id` for
cross-trace correlation.

**User-emitted logs from within nodes.** Logs emitted by user code inside a node function
participate in the same correlation rules: if the user uses the language's stdlib logger
(Python `logging`, TypeScript console/winston/pino), the OTel Logs Bridge handles attribution
transparently. If the user uses a custom logger that isn't bridged to OTel, framework
correlation is best-effort — the spec contract applies to logs that flow through the OTel
Logs SDK.

## 8. Langfuse mapping

This section specifies the **Langfuse** backend mapping, sibling to the OpenTelemetry mapping in
§3–§7. Implementations that emit Langfuse data directly (a "Langfuse observer") follow the rules
below. The mapping consumes the same §6 observer event stream as the OTel mapping — a graph MAY
have both observers attached, and each one is a self-contained consumer of the event stream.

The OTel mapping remains the reference shape for cross-backend equivalence (§1). When a graph is
wired to BOTH observers, the same OA-state appears in both backends; users join by
`correlation_id` (§3) to follow a single invocation across them.

### 8.1 Purpose

The Langfuse mapping defines how OA's runtime event surface maps to Langfuse's native data
model — Traces, Observations (Generation, Span, Event), and the Prompt entity — without going
through Langfuse's OTLP ingest. Direct emission via the Langfuse client preserves the full
fidelity of Langfuse's native shape (first-class Generation rendering, true Prompt-entity links,
Langfuse-shaped metadata) where OTLP-then-ingest produces lossy translation through string-valued
OTel attributes.

This mapping covers the Trace + Observation surface. Langfuse Sessions, Scoring, and Cost
surfaces are deferred (§8.10).

### 8.2 Langfuse data model

Langfuse exposes a small set of entity types relevant to this mapping:

- **Trace.** Top-level container for one logical interaction. Carries identity (`id`), metadata
  (`name`, `userId`, `sessionId`, `tags`, `version`, arbitrary `metadata` map), JSON-typed
  `input` / `output` payload fields surfaced as headline columns in the Langfuse Traces list
  view, and contains a tree of Observations.
- **Observation.** A unit of work nested under a Trace. Three concrete types:
  - **Span.** Generic timed work — node executions, subgraph dispatch, fan-out dispatch.
  - **Generation.** LLM call. Adds `input`, `output`, `model`, `modelParameters`, `usage`,
    `prompt` (link to a Prompt entity) on top of the base Span fields.
  - **Event.** Point-in-time signal with no duration. Not used by this mapping; reserved for
    future proposals.
- **Prompt entity.** A Langfuse-managed prompt record with `name`, `version`, `label`, and
  content. Generation observations carry a native link to a Prompt entity when the prompt's
  source provides one (see §8.4.4 for the linkage trigger).

Implementations consume Langfuse's client SDK in their host language (Python, TypeScript). The
SDK calls themselves are implementation detail; this mapping constrains the **shape that lands
in Langfuse**, not the SDK method names.

### 8.3 Observation-type mapping

Each OA span type (per §4 of the OTel mapping) translates to a Langfuse entity per the table
below.

| OA span type | Langfuse entity |
|---|---|
| Invocation span (§4) | Trace (the container itself; no top-level Span observation wraps it) |
| Node span (§4) | Span observation, child of the Trace or the surrounding parent Span |
| Subgraph span (§4.3) | Span observation, child of the surrounding parent Span; contains the subgraph's nested node Span observations |
| Fan-out node span (§4) | Span observation (the dispatch span; contains the per-instance Span observations) |
| Fan-out instance span (§4.3) | Span observation, child of the fan-out node Span |
| LLM provider span (§5.5) | Generation observation |
| Retry attempt spans (§4) | Sibling Span / Generation observations (one per attempt) under the same parent; per-attempt attribution uses the metadata.attempt_index key (§8.4) |

The invocation maps to the Trace (the container) rather than to a top-level Span observation.
Rationale: Langfuse's Trace IS the root container; introducing an additional Span observation
under the Trace duplicates the root and creates an extra layer the UI must render. The
trace-level metadata fields (§8.4) carry the OA invocation attributes that would otherwise live
on a root span.

### 8.4 Attribute mapping table

The §5 OA attribute keys translate to Langfuse fields per the tables below. Implementations MUST
set the corresponding Langfuse fields when the source OA attribute is set on the source span
(per §5).

**Shared top-level namespace with caller metadata.** The Langfuse mapping writes OA-emitted
observability fields as top-level keys of `trace.metadata` / `observation.metadata` /
`generation.metadata` — the same top level where §3.4 caller-supplied metadata keys land. Both are
placed at the top level deliberately: Langfuse filters reliably only on top-level metadata keys. To
keep both sets filterable without collision, §3.4 reserves the OA-emitted key names (listed there)
so a caller key cannot occupy the same metadata key as an OA-emitted field. OA-emitted keys are NOT
nested under a sub-object — that would place them where Langfuse filtering does not reach.

Per §3.4, the Langfuse mapping is one specific instance of the per-backend propagation pattern
for caller-supplied invocation metadata. Langfuse's data model treats `trace.metadata` and
`observation.metadata` as typed top-level fields separate from OTel span attributes; the
Langfuse observer must populate them explicitly. OTel-attribute-based backends (Phoenix /
Arize, Honeycomb, Datadog APM, HyperDX) do NOT need this per-backend propagation; they inherit
the §5.6 `openarmature.user.*` cross-cutting attributes from the OTel observer's span
emission.

**Distinction from Langfuse Sessions.** Langfuse's `trace.metadata` field (the target of
§3.4's caller-supplied metadata propagation) is distinct from Langfuse's Sessions feature.
Sessions group multiple traces under a single `sessionId` for cross-invocation conversation
replay; they are deferred to a future sessions capability (see §10 *Out of scope*). §3.4's
caller-supplied metadata is per-invocation arbitrary key/value enrichment used for filtering
and search; metadata entries are NOT promoted to Langfuse's `userId` / `sessionId` Trace
fields by these propagation rules. The two surfaces are complementary and orthogonal.

**Langfuse-specific constraints on caller-supplied metadata.** Langfuse's documentation
states that propagated metadata keys are limited to alphanumeric characters, and that
string-valued entries are limited to 200 characters. Non-string scalar values (int, float,
bool) and homogeneous arrays — all permitted by §3.4 — propagate per the Langfuse SDK's
native handling (typically preserved as their native type in the metadata payload; the
200-character limit does not apply to non-string scalars). Callers wiring OA to a Langfuse
backend SHOULD use alphanumeric keys (e.g., camelCase like `tenantId`) and keep
string-valued entries within Langfuse's 200-character bound. The OA API-boundary
validation does NOT enforce these constraints by default (they are Langfuse-specific, not
spec-wide per §3.4 cross-backend portability); a key or value that violates Langfuse's
constraints reaches the Langfuse observer and is handled per the Langfuse SDK's error /
truncation semantics. Implementations MAY expand their `invoke()`-boundary rejected-key set
to also catch Langfuse-specific constraints early, per §3.4's MAY-expand allowance.

#### 8.4.1 Trace-level mapping (sourced from invocation span attributes)

| OA attribute (per §5.1, §5.6) | Langfuse Trace field |
|---|---|
| `openarmature.invocation_id` | `trace.id` — a 128-bit id as 32 lowercase hex. A UUID `invocation_id` maps to its hex form (dashes stripped); a non-UUID value maps to a deterministic `SHA-256`-based derivation, with the raw id also written to `trace.metadata.invocation_id`. See the *`trace.id` derivation* note below the table. |
| `openarmature.correlation_id` | `trace.metadata.correlation_id` AND propagated to every observation's `metadata.correlation_id` per §8.5 |
| `openarmature.graph.entry_node` | `trace.metadata.entry_node` |
| `openarmature.graph.spec_version` | `trace.metadata.spec_version` |
| `openarmature.implementation.name` | `trace.metadata.implementation_name` |
| `openarmature.implementation.version` | `trace.metadata.implementation_version` |
| (caller-supplied invocation label OR entry node name, per §8.6) | `trace.name` |
| §4.4 detached-mode dispatch context: the parent invocation's `invocation_id` | `trace.metadata.detached_from_invocation_id` — emitted on the detached child trace only (a trace produced by detached-mode dispatch per §4.4). Points back to the parent invocation for inverse lookup. Sibling to `trace.metadata.correlation_id` (preserved across detached / parent traces per §3.1, providing the forward direction). Absent on non-detached traces. |
| Each entry `(key, value)` in the in-scope caller-supplied invocation metadata at trace emission time (per §3.4, including any mid-invocation augmentations applied before trace closure) | `trace.metadata.<key>` (top level, sibling to `correlation_id` / `entry_node` / `spec_version`; NOT nested under a `user` sub-object so Langfuse UI filtering on `metadata.<key>` matches what callers supplied; implementations SHOULD use Langfuse SDK's `trace.update(metadata=...)` to apply mid-invocation augmentations to the open Trace) |
| `initial_state` at invocation entry — sourced via the *Trace input/output sourcing* paragraph below | `trace.input` |
| Final state at invocation exit — sourced via the *Trace input/output sourcing* paragraph below | `trace.output` |

**`trace.id` derivation (caller-supplied `invocation_id`).** Langfuse (OTel-based) requires
`trace.id` to be a 128-bit value rendered as 32 lowercase hex characters. Per §5.1 the
`invocation_id` MAY be caller-supplied and need not be a UUID, so the Langfuse mapping derives
`trace.id` as follows:

- **`invocation_id` is a valid UUID:** `trace.id` = the UUID's 32-character lowercase hex form
  (dashes stripped). Direct lookup by `invocation_id` works (strip dashes to search).
- **`invocation_id` is not a UUID:** `trace.id` = the first 16 bytes of `SHA-256(invocation_id)`
  (UTF-8 bytes), rendered as 32 lowercase hex. The raw `invocation_id` is ALSO written to
  `trace.metadata.invocation_id` so lookup by the caller's original value works via Langfuse
  metadata filtering (a top-level metadata key). The derivation MUST be deterministic and stable
  across implementations.

This non-UUID derivation is exactly Langfuse's own `create_trace_id(seed)` helper
(`sha256(seed.encode("utf-8")).digest()[:16].hex()`), so the derived `trace.id` equals
`create_trace_id(seed=invocation_id)` — a consumer can reproduce or look up the trace id from its
raw id via the helper. (`trace.metadata.invocation_id` is reserved against caller-metadata
collision per §3.4.)

**Trace input/output sourcing.** Trace-level input/output emission is governed by a
Langfuse-observer-level privacy knob and a three-lever decision tree.

**`disable_state_payload: bool`** — Langfuse-observer-level opt-out for Trace-level `input` /
`output` payload emission. Default ON, mirroring §5.5.4's `disable_llm_payload` privacy-safe
posture. When ON, the observer does NOT serialize `initial_state` / final state directly onto
`trace.input` / `trace.output`; the default-off minimal stub (below) applies unless a caller
hook overrides. When OFF, the observer serializes `initial_state` → `trace.input` and final
state → `trace.output`, subject to the existing payload-byte-cap truncation (§5.5.5). The two
payload-privacy knobs (`disable_llm_payload` from §5.5.4 and the new `disable_state_payload`
here) are independent: the former controls Generation-level input/output; the latter controls
Trace-level input/output. Implementations MAY expose them as a single combined flag for
convenience, but the spec defines them as two separate concerns so callers can opt one in
without the other — they're independent concerns with different threat models (LLM payload =
model interaction transcript; Trace-level state payload = application state shape).

The Trace-level input/output sources resolve via the following decision tree, applied
independently to each of `trace.input` and `trace.output`:

1. **Caller hook supplied AND returns a non-null value** → the hook's return value is
   serialized to the Trace field.
2. **`disable_state_payload` is OFF** → the raw state object (`initial_state` for input, final
   state for output) is serialized to the Trace field, subject to the existing
   payload-byte-cap truncation.
3. **Otherwise (default)** → the minimal stub:
   - `trace.input` = `{"entry_node": <entry node name>, "correlation_id": <correlation ID>}`.
   - `trace.output` = `{"final_node": <name of the node whose execution preceded the
     END-reached transition, or that raised>, "status": <status enum below>}`.

The minimal stub carries no application payload — `entry_node` is the graph's declared entry
node name (already emitted as `trace.metadata.entry_node` above) and `correlation_id` is the
invocation's correlation ID (already emitted as `trace.metadata.correlation_id` per §8.5);
`final_node` is the graph-level identifier of the last node executed, not the node's payload.
The stub is therefore privacy-safe by construction.

**`status` enum.** The stub `trace.output.status` MUST be one of:

- `"completed"` — invocation reached END normally.
- `"failed"` — invocation raised at any node, edge, reducer, or boundary validator before
  reaching END.

The enum is closed at this spec version. Future proposals may extend it (e.g., suspension
states once that capability lands) via the same maintenance discipline §8.4's emitted-key set
uses.

**Caller-hook contract.** Implementations MAY expose two optional hook callables on the §8
LangfuseObserver construction surface (per-language idiomatic naming and shape — keyword
constructor arguments, configuration record fields, builder methods, etc.; the spec defines the
contract, not the surface syntax):

- `trace_input_from_state(state) → InputValue | None` — called once per invocation, at
  invocation entry, after the engine has constructed `initial_state` and before any node runs.
  Takes the raw state object (the typed-state instance in language-idiomatic form). Returns
  the value to use as `trace.input`. Returning the language's null sentinel falls through to
  the next lever in the decision tree.
- `trace_output_from_state(state) → OutputValue | None` — called once per invocation, at
  invocation exit, after the engine has produced the final state (whether the invocation
  reached END or failed). Same signature shape; falls through to the next lever on null.

Hook return types: any JSON-serializable value (object, array, primitive, or string).
Implementations MUST apply the existing payload-byte-cap truncation if a hook's return value
exceeds the cap.

Hook signature takes the raw state, not a typed wrapper or `NodeEvent` — minimum added surface
area, consistent with the framework's "transparency over abstraction" framing.

**Resume semantics.** On a resumed invocation (`invoke(resume_invocation=...)` per
pipeline-utilities §10.4), the framework mints a fresh `invocation_id` and therefore a fresh
Langfuse trace per the *`trace.id` derivation* note above. The hooks fire on the resumed
invocation as if it were a new invocation, writing to the resumed trace's `input` / `output`.
They do NOT overwrite the original (now-completed) trace's fields — Langfuse trace identity is
per-`invocation_id`, and the resumed trace is a separate Langfuse object. The `correlation_id`
is preserved across the original and resumed traces (per §3.1), so the operator can correlate
the resume to its original via metadata filtering.

**Implementation surface caveat.** Implementations bind the §8.4.1 contract to whichever vendor
SDK method projects trace-level input / output values into the Langfuse UI's headline Input /
Output columns. As of Langfuse SDK v4 (empirically verified 2026-05-31), this is the
`set_current_trace_io` / `Span.set_trace_io` family, which the SDK marks as deprecated with
stated removal in a future major version. The non-deprecated `propagate_attributes` method does
not currently project trace-level input / output values to the headline columns. The §8.4.1
contract (three-lever decision tree, hook contract, status enum, resume semantics) is
independent of which SDK method populates the values and remains stable across SDK migrations;
implementations track vendor SDK releases for migration-path updates. The operational tracking
record — verified-against SDK version, per-row re-verification cadence — lives at
`docs/compatibility.md` per the *External-dependency adoption* policy (`GOVERNANCE.md`); the
caveat above and the compatibility-page row are kept in sync when re-verification updates
either.

#### 8.4.2 Observation-level mapping (sourced from node / subgraph / fan-out span attributes)

| OA attribute (per §5.2, §5.3, §5.4, §5.6) | Langfuse Observation field |
|---|---|
| `openarmature.node.name` | `observation.name` |
| `openarmature.node.namespace` | `observation.metadata.namespace` (string array preserved as-is) |
| `openarmature.node.step` | `observation.metadata.step` |
| `openarmature.node.attempt_index` | `observation.metadata.attempt_index` |
| `openarmature.node.fan_out_index` | `observation.metadata.fan_out_index` (when present) |
| graph-engine §6 NodeEvent `branch_name` (per parallel branches, proposal 0011) | `observation.metadata.branch_name` (when present, per-branch Span observation; sibling to `fan_out_index` for parallel-branches disambiguation, the same role `fan_out_index` plays for fan-out). Absent on observations from nodes outside any parallel-branches subgraph. |
| `openarmature.subgraph.name` | `observation.metadata.subgraph_name` (when present) |
| `openarmature.fan_out.item_count` | `observation.metadata.fan_out_item_count` (fan-out node Span observation only) |
| `openarmature.fan_out.concurrency` | `observation.metadata.fan_out_concurrency` (fan-out node Span observation only) |
| `openarmature.fan_out.error_policy` | `observation.metadata.fan_out_error_policy` (fan-out node Span observation only) |
| `openarmature.fan_out.parent_node_name` | `observation.metadata.fan_out_parent_node_name` (fan-out instance Span observation only) |
| §4.4 detached-mode: dispatching observation marks itself when it fires a detached child | `observation.metadata.detached` — boolean `true` on the parent-side dispatching observation that dispatches a detached subgraph or fan-out instance. Absent (or `false`) on non-dispatch observations and on observations that dispatch non-detached children. |
| `openarmature.correlation_id` | `observation.metadata.correlation_id` (cross-cutting per §8.5) |
| Each entry `(key, value)` in the in-scope caller-supplied invocation metadata at the observation's emission time (per §3.4) | `observation.metadata.<key>` on EVERY Observation (top level, same propagation rationale as `correlation_id`; lets users filter across observations from detached subgraphs / fan-outs in one Langfuse UI query). For the fan-out per-instance use case, each instance's observations carry that instance's augmented metadata (per §3.4 per-async-context scoping), so adopters can filter Langfuse by the per-instance identifier (e.g., `productId`) to find that specific instance's subtree. |
| `openarmature.error.category` | `observation.level = "ERROR"`, `observation.statusMessage = <category>` |

#### 8.4.3 Generation-specific mapping (sourced from LLM provider span attributes)

Generation observations inherit the §8.4.2 observation-level mapping above (name, metadata.*,
level/statusMessage). The fields below are additional, specific to Generations.

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

When a generation's finish_reason is an error condition (e.g., `"content_filter"`, `"length"` —
vendor-specific), the implementation MAY also set `observation.level = "WARNING"` to surface the
condition in the Langfuse UI; this is RECOMMENDED but not MUST (different vendors carry
different "soft error" semantics, and the OA error category mechanism in §4.2 covers hard
failures via the `openarmature.error.category` mapping above).

#### 8.4.4 Prompt linkage mapping (sourced from prompt-management §11 attributes)

When the LLM provider span carries `openarmature.prompt.*` attributes (per prompt-management
§11), the Generation observation MUST surface the prompt identity. The mechanism depends on what
the prompt's source backend provides — not on which specific backend it is. Two cases:

1. **The prompt's source exposes a Langfuse Prompt reference.** Any prompt backend that attaches
   an accessible Langfuse Prompt entity to the rendered prompt qualifies. A Langfuse-native
   PromptBackend is the obvious case, but the contract is open to other backends that may expose
   the same — e.g., a federated proxy backend that resolves through Langfuse, a custom backend
   that mirrors prompts to Langfuse, or any future backend that interoperates with the Langfuse
   Prompt entity. In all such cases the Generation observation MUST be linked to that Langfuse
   Prompt entity via Langfuse's native link mechanism (the Generation API accepts a prompt
   reference; the SDK call shape is implementation detail). The metadata fields below MUST also
   be set redundantly so consumers can query without traversing the link.
2. **The prompt's source does NOT expose a Langfuse Prompt reference.** This covers all backends
   that have no native Langfuse Prompt counterpart — filesystem, in-memory, and any other
   non-Langfuse-aware backend (current or future). No Prompt-entity link is established;
   identity surfaces via metadata only.

The trigger for case 1 versus case 2 is whether a Langfuse Prompt reference is available on the
prompt record at emission time. As of v0.26.0 (prompt-management proposal 0033), the reference
lives at a spec-defined location: `Prompt.observability_entities['langfuse_prompt']`. When the
key is present (value is the opaque Langfuse SDK Prompt reference), case 1 applies; when the
key is absent or `observability_entities` is `None`, case 2 applies. The Langfuse observer
MUST establish the link when the reference is present and MUST NOT fabricate one when absent.

In both cases the following metadata is set:

| OA attribute (per prompt-management §11) | Langfuse Generation field |
|---|---|
| `openarmature.prompt.name` | `generation.metadata.prompt.name` |
| `openarmature.prompt.version` | `generation.metadata.prompt.version` |
| `openarmature.prompt.label` | `generation.metadata.prompt.label` |
| `openarmature.prompt.template_hash` | `generation.metadata.prompt.template_hash` |
| `openarmature.prompt.rendered_hash` | `generation.metadata.prompt.rendered_hash` |

The `generation.metadata.prompt` map's shape is normative for cross-implementation parity.
Implementations MUST NOT collapse it into flat metadata keys (e.g., `metadata.prompt_name` flat
strings) when the structured shape above is available — the structured form lets Langfuse UI
extensions render prompt identity uniformly.

**Prompt-group propagation.** When `openarmature.prompt.group_name` is set on spans participating
in a `PromptGroup` (per prompt-management §9 / §11), the value propagates to
`observation.metadata.prompt_group_name` on every participating observation — including each
Generation observation for the group's LLM calls and any wrapping node/subgraph Span observations
carrying the group_name. Unlike the per-Generation prompt-identity fields above, this is an
observation-level attribute and follows the §8.4.2 observation-level mapping pattern.

### 8.5 Correlation ID realization

The cross-backend correlation ID (§3) surfaces in Langfuse at two levels:

- **Trace-level metadata.** Each Trace's `metadata.correlation_id` MUST carry the invocation's
  correlation ID. Users querying Langfuse for traces matching a correlation ID found in their
  OTel logs filter here.
- **Observation-level metadata.** Each Observation (Span, Generation) MUST also carry
  `metadata.correlation_id`. Observations from detached subgraphs and detached fan-outs (per
  §4.4) live in separate Traces but share the same correlation ID with the parent invocation;
  observation-level metadata lets users filter across all of them in one query without first
  finding the related Traces.

Detached trace mode (§4.4) applies to the Langfuse mapping the same as to the OTel mapping. A
detached subgraph or fan-out produces a separate Langfuse Trace (new `trace.id`); the parent's
dispatch observation carries a Langfuse-native cross-trace reference in its metadata
(`metadata.detached_child_trace_ids` — string array, one entry per detached child). The
correlation_id is invocation-scoped per §3, so all detached Traces and the parent Trace share
the same `metadata.correlation_id`.

### 8.6 Trace name

The Langfuse Trace MUST carry a `trace.name` field. This is the human-readable identifier the
Langfuse UI surfaces in trace lists and search results; meaningful trace names are how users find
their work in the UI.

The trace-name source is one of:

1. **Caller-supplied invocation label.** Implementations MUST support a per-invocation
   caller-supplied label that maps to `trace.name`. The mechanism (keyword argument to
   `invoke()`, field on the invocation config record, equivalent per-language convention) is
   implementation-defined; the behavioral contract is that the caller has a way to set it.
2. **Entry-node name fallback (RECOMMENDED default).** When the caller supplies no invocation
   label, implementations SHOULD default `trace.name` to the graph's entry-node name (already
   exposed via `openarmature.graph.entry_node`). Falling back to entry-node name gives Langfuse
   traces a meaningful default label without requiring callers to thread an extra argument
   through every `invoke()` call.

Implementations MAY support additional sources (e.g., a registered trace-name resolver function
on the observer) at their discretion; the behavioral contract above is the minimum.

### 8.7 Generation rendering

Generation observations render the LLM call's input/output content when the Langfuse observer's
`disable_llm_payload` flag is `False`. The flag governs Langfuse-side emission only; it is
independent of the OTel observer's flag per §8.9. Both observers consume the same source data
(per §5.5's definition of LLM-payload content) from the §6 LLM provider event, and each makes
its own emission decision.

The Langfuse observer MUST support its own `disable_llm_payload` flag independent of the OTel
observer's setting (per §8.9). When the flag is `False`, the observer:

- Parses the §5.5.1 `openarmature.llm.input.messages` JSON string back to the native message-list
  structure (per llm-provider §3 message shape) and sets `generation.input` to the parsed
  structure.
- Sets `generation.output` from `openarmature.llm.output.content` verbatim.
- Sets `generation.metadata.request_extras` from `openarmature.llm.request.extras` (parsed back
  from JSON).

When the flag is `True` (default), `generation.input`, `generation.output`, and
`generation.metadata.request_extras` MUST NOT be set on the Generation observation. Other fields
(model, modelParameters, usage, metadata.system, metadata.response_model, metadata.response_id,
prompt linkage) continue to emit per §8.4.3 and §8.4.4 regardless of the payload flag.

**Truncation contract.** The §5.5.5 per-attribute byte cap applies to the OA-attribute source
values; when the source attribute is truncated, the Langfuse observer receives the
already-truncated string (the OTel and Langfuse observers MAY share the same truncation
implementation upstream). The Langfuse observer:

- Sets `generation.input` / `generation.output` / `generation.metadata.request_extras` to the
  truncated value as-is when the source string ends with the §5.5.5 truncation marker
  (`…[truncated, M bytes total]`). For `generation.input` and `generation.metadata.request_extras`
  (which are intended to be structured objects in Langfuse, not strings), the truncated form is
  not parseable JSON — the observer MUST set those fields to the raw truncated string in that
  case, preserving the marker; the Langfuse UI surfaces this as a string rather than a structured
  view. This matches the §5.5.5 design intent: the unparseable JSON IS the truncation signal.

**Inline-image redaction.** The §5.5.5 inline-image redaction rule applies identically — inline
image bytes never reach Langfuse, only the placeholder `{type: "image", source: {type:
"inline_redacted", byte_count: N}, media_type, detail?}` record does. This is a hard rule,
ungated by `disable_llm_payload`.

### 8.8 Prompt linkage

Per §8.4.4. The two cases (prompt source exposes a Langfuse Prompt reference vs. does not)
determine whether a Prompt-entity link is established in addition to metadata. The metadata shape
is normative for cross-implementation parity; the link establishment is conditional on the
source's capability, not on any specific backend identity.

The propagation mechanism — how `openarmature.prompt.*` attributes reach the LLM provider span
at emission time — is the prompt-management capability's concern (§11 of prompt-management; the
mechanism is implementation-defined). This mapping consumes the attributes once they're on the
span.

### 8.9 Composition with OTel

The Langfuse observer and the OTel observer are independent §6 event consumers. A graph MAY have
both attached; both MAY emit during the same invocation.

Each observer's behavior is governed by its own configuration:

- **`disable_llm_spans`** — each observer supports the flag independently. Setting
  `disable_llm_spans=True` on one observer does NOT suppress emission on the other. Use case: a
  user has external auto-instrumentation writing OTel spans for LLM calls and also wants the
  Langfuse observer to emit Generations natively; they set `disable_llm_spans=True` on the OTel
  observer (so OA doesn't duplicate the external library's spans) and leave it `False` on the
  Langfuse observer (so Generations still emit to Langfuse).

- **`disable_llm_payload`** — each observer supports the flag independently. A user MAY emit full
  payload to Langfuse (their canonical generation-rendering tool) while keeping OTel-side payload
  off (cost / size reasons). Defaults: `True` for OTel per §5.5.4, `True` for Langfuse for
  symmetric privacy posture.

- **`disable_genai_semconv`** — only meaningful to the OTel observer per §5.5.4. The Langfuse
  observer does not emit GenAI semconv attributes (it uses Langfuse-native fields); the flag is
  ignored by the Langfuse observer.

The cross-backend correlation ID (§3) is the join key. A user filtering by `correlation_id` in
Langfuse can find the same `correlation_id` in their OTel logs (HyperDX, Datadog) and pivot
between the two views of one invocation.

**Unified Langfuse configuration.** Implementations SHOULD allow a single Langfuse client
configuration (host, public key, secret key, or equivalent) to be shared across any
Langfuse-consuming surfaces the implementation exposes — the Langfuse observer, a Langfuse-aware
PromptBackend, and any future Langfuse-aware capability the implementation adds. The API shape
is implementation-defined; the behavioral contract is that the user configures Langfuse
credentials once and all Langfuse-consuming surfaces use them.

### 8.10 Out of scope

Not covered by this section; deferred to follow-on proposals:

- **Langfuse Sessions.** Langfuse's `userId` / `sessionId` Trace fields support cross-trace
  grouping. Cross-invocation session identity is proposal 0020's concern; once that lands,
  `trace.sessionId` realization follows.
- **Langfuse Scoring.** Quality scoring of Generations / Traces is a separate surface that the
  OA spec does not currently address. A future `openarmature.score.*` attribute family and
  corresponding Langfuse `score` API call would land via a separate proposal.
- **Langfuse Cost / Custom token pricing.** Cost computation belongs to the Langfuse-side or to
  a future OA cost-tracking capability; this mapping uses Langfuse's standard `usage` shape only.
- **LangfusePromptBackend caching policy.** Backend-side caching is permitted by
  prompt-management §5 and is implementation-defined; this mapping does not constrain it.

## 9. Queryable observer pattern

The `Observer` protocol (per graph-engine §6) is intentionally minimal — a single async callable
receiving node events from the strictly-serial delivery queue. **Concrete observer types MAY
expose additional read methods** on the instance attached to the graph; pipeline nodes MAY hold
a reference to the observer they attached and consume those methods at runtime.

This section describes the pattern's normative constraints. It does NOT add new abstract surface
to the `Observer` protocol itself — the protocol's single async-callable shape is unchanged. The
pattern is a convention for how concrete observer implementations expose read-augmenting state
to the pipeline.

### 9.1 Read-method contract

Read methods on a queryable observer MUST be:

- **Query-only.** No graph state mutation (the pipeline state is managed exclusively by the
  graph engine; observers MUST NOT modify it).
- **No routing side effects.** The observer's read MUST NOT influence edge resolution,
  conditional branching, or node dispatch.
- **No observer-side emission.** Read methods MUST NOT emit events to other observers, directly
  or indirectly. The observer's role in the event stream is event consumption (via the
  `Observer.__call__` surface); cross-observer notification would create ordering dependencies
  the spec does not establish.
- **Non-blocking from the event-loop perspective.** Read methods SHOULD be local-state accesses
  (synchronous reads against in-memory data the observer accumulated). If a method must perform
  I/O (e.g., a cached remote lookup), it SHOULD use the event loop's non-blocking primitives and
  document the latency expectations so callers can decide whether to call from within a node
  handler. The spec does not forbid I/O outright — implementations that expose I/O-backed reads
  accept responsibility for the latency envelope.

Queryable observers are a **read-augmenting** convenience for patterns where pipeline
computation depends on cross-cutting data derived from event emissions (per-node usage
summaries, per-node latency rollups, per-node error counts). They are NOT a replacement for
State — see *Three-channel data-access guidance* (§9.3 below).

### 9.2 Async-safety contract

Read methods on a queryable observer MAY race with concurrent event emission to the same
observer. Implementations MUST ensure the observer's internal state is **read-consistent** — a
read MUST NOT return a torn or partially-mutated view (no half-updated dictionaries, no
inconsistent counter pairs) — but they MUST NOT guarantee that a read sees all events emitted up
to a particular point in wall-clock time.

A consumer that needs **post-completion stability** (e.g., a final-summary node that wants to
read after every event for the invocation has been delivered) MUST gate the read on observing
the invocation's completion signal (the strictly-serial observer delivery queue per graph-engine
§6 guarantees prior events are delivered before the invocation's terminal event reaches the
observer). Implementations MAY offer stricter guarantees as concrete-observer features (e.g., a
`get_stable_total()` accessor that blocks until completion); the spec defines the floor.

### 9.3 Three-channel data-access guidance

Pipelines have three distinct read surfaces for data accumulated across an invocation. Use the
right one for the use case:

| Channel | Shape | Use when |
|---|---|---|
| **State** (graph-engine §2) | Typed schema with declared reducers; participates in graph routing; survives checkpoint / resume; canonical mutable data plane | Pipeline computation data; data the next node's behavior depends on; data that needs to round-trip through reducers; data that needs to survive a crash |
| **Invocation metadata** (§3.4) | Untyped per-invocation key/value channel; cross-cutting attribution; per-async-context scoped (read via `get_invocation_metadata()`) | Span / trace attributes; user / request IDs; audit context; values that don't belong in the typed schema; cross-cutting attribution consumed by one end-of-invocation node |
| **Queryable observer accumulator** (this section) | Derived summary state on a concrete observer instance; queried via read methods at runtime | Per-node summaries derived from event emissions (usage tokens per node, latency per node, retry count per node); when adding the summary as a State field would force reducer-shape pollution |

**Default: prefer State.** State is the canonical mutable data channel for pipeline computation.
Invocation metadata and queryable observer accumulators are narrow carve-outs.

**Invocation metadata** is the right answer when:

- The data is cross-cutting attribution (user, request, audit context), AND
- Adding the data as a State field would be schema pollution, AND
- The data doesn't need reducer semantics, AND
- The data doesn't survive across invocations.

**Queryable observer accumulator** is the right answer when:

- The data is a derived summary (counts, sums, ratios) over event emissions, not raw input, AND
- Adding the summary as a State field would force schema pollution (incompatible reducer
  shapes, fan-out vs non-fan-out asymmetry, etc.), AND
- The consuming node is downstream of the event emissions it needs to read.

The three channels are independent — a real pipeline may use all three. A "persist" node at the
end of an invocation might read its canonical computation results from State, its user
attribution from invocation metadata, and its per-LLM-call token rollup from a queryable
accumulator. The shapes are different; the data lifetimes are different; the spec carves out
each lane explicitly to keep them from blurring.

### 9.4 Lifecycle

This subsection's rules apply only to queryable observers that accumulate per-invocation state
(e.g., per-node-summary accumulators). Observers that expose query methods over non-accumulated
data (e.g., a pass-through inspector that returns the latest event seen) are not subject to the
lifecycle rules below.

Accumulating queryable observers MUST NOT auto-drop accumulated state on the invocation's
completion signal — an end-of-invocation reader (typically a "persist" or "summary" node running
as the final invocation step) legitimately needs to read the bucket BEFORE the invocation
completes; auto-drop on the completion signal would race against the read.

Concrete accumulating observers MUST provide an **explicit drop / cleanup mechanism** — a method
that releases the accumulated state for a given invocation (e.g., `drop(invocation_id)` in
Python; per-language idiomatic equivalents). The consuming node calls drop after reading.
Implementations SHOULD document the cleanup discipline in the observer's API documentation.

Long-lived accumulators (an observer that survives across many invocations) accumulate buckets
per `invocation_id` until explicitly dropped — this is a feature (session-scoped accumulators
surviving across resumes) and a cost (memory pressure if drops are missed). The spec does NOT
mandate a maximum retention policy; concrete accumulating observers MAY offer ergonomic safety
features (e.g., LRU eviction, TTL-based cleanup) on top of the spec contract.

## 10. Determinism

OTel span content is a function of (a) the §6 observer event stream and (b) implementation-specific
data (timestamps, span IDs, trace IDs). The graph-engine §5 determinism guarantee covers the §6
event stream — for the same input, the same events fire in the same order with the same payloads.
The implementation-specific data (IDs, timestamps) is inherently nondeterministic and is therefore
NOT covered by determinism guarantees.

Langfuse observation content (per §8) is similarly a function of (a) the §6 observer event stream
and (b) implementation-specific data (timestamps, observation IDs, trace IDs); the same determinism
boundary applies — the deterministic portion of observation content is covered, the
implementation-specific data is not.

The conformance suite asserts determinism over the *deterministic* portion of span / observation
content: hierarchy, names, attributes / metadata (excluding timing-derived ones), and status. It
does NOT assert exact timestamps or IDs.

## 11. Out of scope

Not covered by this specification; deferred to follow-on proposals or sibling sections of this
spec:

- **Custom backends** — users may emit any custom backend by implementing observers and middleware
  that consume the §6 stream and the spec doesn't constrain those.
- **Sampling** — OTel sampling is configured at the SDK level, outside the framework's contract.
  Implementations MAY hint via `record_exception` and span priority but the contract here is on
  the structure of emitted spans, not on whether to emit them.
- **Metrics** — OTel metrics (counters, histograms) for graph-level operations. The current spec
  is trace-only.
- **Baggage and context propagation** — OTel baggage for request-ID-style propagation across
  service boundaries. Defer until a concrete cross-service use case surfaces.
- **Span links** — OTel span links between traces (e.g., for batch operations that accumulate
  inputs from many traces). Defer until needed.

