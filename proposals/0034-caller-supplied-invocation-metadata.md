# 0034: Observability — Caller-Supplied Invocation Metadata Propagation

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-05-26
- **Accepted:** 2026-05-26
- **Targets:** spec/observability/spec.md (extends §3 *Cross-backend correlation ID* with a sibling caller-supplied metadata surface; extends §5.6 *Cross-cutting attributes* with an `openarmature.user.*` cross-cutting attribute family; extends §8.4.1 *Trace-level mapping* and §8.4.2 *Observation-level mapping* with Langfuse propagation rules); spec/graph-engine/spec.md (small clarifying touch to §3 noting `invoke()` accepts an optional `metadata` argument alongside the existing per-language invocation surface)
- **Related:** 0007 (observability OTel span mapping), 0024 (LLM span payload + GenAI semconv), 0031 (observability Langfuse mapping)
- **Supersedes:**

## Summary

Add a normative caller-supplied invocation-metadata surface to
observability. Callers attach an arbitrary key/value mapping at
`invoke()` time (alongside the existing `correlation_id` and
invocation-label surfaces); the framework propagates the entries to
every observability backend the implementation emits to.

The primary cross-vendor propagation is the **OTel mapping**: each
entry becomes a cross-cutting span attribute under the
`openarmature.user.<key>` namespace. Every span in the invocation
carries the full set (same cross-cutting pattern as
`openarmature.correlation_id` per §5.6). Observability backends that
consume OTel spans — Phoenix / Arize, Honeycomb, Datadog APM,
HyperDX, Grafana Tempo / Cloud Trace / etc. — pick up the metadata
uniformly from the span-attribute layer with no per-backend wiring.
This is the surface this proposal defines normatively, and it covers
the majority of observability-backend wiring today.

Backends whose data model carries trace-level metadata as a separate
typed field (not just as OTel span attributes) require an additional
backend-specific propagation rule in their respective §-section of
this spec. **Langfuse** is the one such backend currently specified:
entries merge into the Langfuse `trace.metadata` AND into every
`observation.metadata` (top-level keys) so per-observation filters
in the Langfuse UI work, including across detached subgraphs and
fan-out instances. Future observability backend mappings that need
their own propagation rules add them in their own §-section;
OTel-attribute-based backends inherit the cross-cutting attributes
without per-backend spec work.

Use case (concrete): a production pipeline attaches
`{"tenantId": "acme-corp", "userId": "u-12345",
"featureFlag": "v2-pipeline"}` to each invocation. Operators search
the observability backend's UI by `tenantId = "acme-corp"` to find
traces for that customer's invocations; they pivot across backends
(e.g., from Langfuse to OTel logs in HyperDX) by the same `tenantId`
to see surrounding infrastructure activity. The pattern is widely
re-derived in adopter code today (each service writes custom
OA-bypassing backend-SDK calls to set trace metadata, or stuffs
identifiers into the `correlation_id` string and parses them out
later). Codifying the surface in spec lets every adopter use the
same path without re-inventing it per backend.

Key/value constraints, namespace reservations, and propagation rules
are normative. The mechanism by which callers supply the mapping at
`invoke()` time is per-language idiomatic (keyword argument; field on
an invocation-config record; equivalent).

## Motivation

Production adopters of proposals 0007 (OTel mapping) and 0031
(Langfuse mapping) routinely need to attach business-domain
identifiers to traces so they can find specific traces by domain
attributes — "find all traces for tenant `acme-corp`", "find the
trace for product `xyz`", "find traces during the `v2-pipeline`
canary." The OA spec today gives them three surfaces for this:

1. **`correlation_id`** — one string per invocation. Callers can
   stuff identifiers into it (`"req-123;tenant-acme;product-xyz"`)
   but observability-backend UIs don't parse it; it's just a
   free-form string match.
2. **Caller-supplied invocation label** (e.g., `langfuse.trace.name`
   per §8.6 of observability) — one string per invocation, on the
   Trace's display name. Not searchable as separate fields.
3. **Per-prompt `Prompt.observability_entities`** (proposal 0033) —
   specific to prompt-entity linkage; not arbitrary domain metadata.

Three patterns recur in adopter code to fill the gap:

- **OA-bypassing backend-SDK calls.** The service calls the
  backend's SDK directly after `invoke()` returns (e.g.,
  `langfuse.trace.update(metadata={...})`,
  `phoenix.set_attributes(...)`, vendor-equivalent). Works for the
  specific backend but bypasses OA's `TracerProvider` isolation (§6
  of observability) and observer-event model; breaks if OA's
  observer wiring changes between versions; doesn't propagate across
  multiple wired backends.
- **Identifier stuffing into `correlation_id`.** The
  `correlation_id` string carries multiple identifiers joined by a
  separator. Searchable only by substring; doesn't render
  meaningfully in any backend UI; loses the per-field filtering UIs
  are designed for.
- **Per-service span-attribute helpers.** Each service writes a
  middleware or observer that sets custom span attributes on every
  span. Works for OTel-based backends but requires
  re-implementation per service and doesn't propagate to backends
  with non-OTel data models (like Langfuse's typed `metadata`
  field).

A spec-supported invocation-metadata surface replaces all three with
one normative path. The framework knows the metadata at `invoke()`
time, propagates it through the existing observer-event model, and
hands it to whichever observability mappings the implementation has
wired in. Adopters set it once, search by it everywhere.

### Why now

The recently-shipped observability + LLM-provider + prompt-management
batch (proposals 0031, 0032, 0033) closes the related surfaces for
production adoption. Without invocation-metadata, the observability
story still has the gap above — adopters who finish absorbing the
batch still need OA-bypassing SDK calls to make traces searchable by
domain identifiers. Landing this proposal alongside completes the
picture.

The surface is small and self-contained (one new caller-side
argument; one cross-cutting attribute family; one Langfuse
propagation rule). It fits naturally as the fourth proposal in the
batch.

## Design

The complete text of the §3 / §5.6 / §8.4 modifications and the
graph-engine §3 touch is reproduced below.

Anticipated bump: MINOR (v0.26.0) — new caller-side surface and new
normative attribute family, no breaking changes.

### observability §3.4 — caller-supplied invocation metadata (new subsection)

In addition to the correlation ID surface (§3.1–§3.3), the framework
MUST accept an optional **caller-supplied metadata mapping** at
invoke time. Callers attach a mapping from string keys to
OTel-attribute-compatible values (a `dict[str, AttributeValue]` in
Python idiom, where `AttributeValue` matches OTel's scalar /
homogeneous-array type contract; equivalent per language) carrying
arbitrary key/value entries that identify the invocation for search
and filtering in observability backends.

**Lifecycle and propagation.** The mapping is per-invocation and
lives for the duration of one outermost `invoke()` call, alongside
the correlation ID. Implementations MUST:

- **Accept the mapping at invoke time** via a per-language
  idiomatic mechanism (e.g., a `metadata` keyword argument on
  `invoke()`, a field on the invocation-config record, equivalent).
- **Propagate via the language's idiomatic context primitive** —
  Python `ContextVar`, TypeScript `AsyncLocalStorage`, equivalents —
  so the mapping is readable from observers without explicit
  threading through function arguments. Same propagation mechanism
  as the correlation ID (§3.1).
- **Reset the context after the invocation completes** so subsequent
  invocations get fresh metadata.

**Key/value constraints.**

- Keys MUST be strings.
- Values MUST be OpenTelemetry-attribute-compatible scalars: string,
  int, float (double), bool, or homogeneous arrays of those types.
  Nested objects, null values, and mixed-type arrays are NOT
  permitted (matching OTel's `AnyValue` attribute-type contract).
- Keys MUST NOT collide with reserved namespaces: `openarmature.*`
  and `gen_ai.*`. Implementations MUST reject (raise an error at the
  `invoke()` API boundary, before any work begins) a metadata
  mapping that contains a colliding key. The error category is
  implementation-defined per the language's API-boundary error idiom
  (Python `ValueError`, TypeScript `RangeError`, Go error return —
  same shape as §6 of graph-engine's drain-timeout-input validation
  per proposal 0030).
- Key length, value length, and entry count are NOT constrained by
  the spec; backends MAY enforce their own limits (Langfuse caps
  trace metadata at a vendor-defined size, etc.) and surface
  rejections via existing error channels.

**Invocation-scoped, not trace-scoped.** Detached subgraphs and
detached fan-outs (per §4.4) inherit the metadata from the parent
invocation. The mapping is per-invocation context, the same as
`correlation_id`; detached children of the invocation share it.

**Mid-invocation augmentation.** Code executing within a node body,
middleware, or observer MAY add entries to the in-scope metadata
mapping during invocation. Implementations MUST expose a per-language
framework helper for this purpose (e.g., a Python
`openarmature.observability.set_invocation_metadata(**entries)`
function; TypeScript equivalent; the spec mandates the behavioral
contract, not the exact API name). The helper:

- Performs an additive merge into the current async context's
  metadata. Existing keys with the same name are overwritten; other
  keys are preserved.
- Validates added keys against the reserved-namespace rule
  (`openarmature.*`, `gen_ai.*`) and the value-type contract above.
  Violations MUST raise at the call site, before any downstream span
  emission picks up the partially-applied state.
- Affects only spans emitted AFTER the call returns. Spans already
  closed are NOT retroactively updated. Spans still open at the time
  of the call (e.g., the invocation span itself, an ancestor node
  span) MAY pick up the additions per OTel's `set_attribute` /
  Langfuse SDK's `trace.update` semantics — implementations SHOULD
  update open spans where the backend SDK supports it, so the
  augmented metadata is visible end-to-end.

**Per-async-context scoping.** The metadata mapping is held in the
language's idiomatic async-context primitive (Python `ContextVar`,
TypeScript `AsyncLocalStorage`) with copy-on-write per async context.
Fan-out instances (pipeline-utilities §9), parallel-branches instances
(§11), and detached children each receive their own copy at dispatch
time; augmentation calls within one instance MUST NOT leak to sibling
instances. This makes the common fan-out pattern (each instance adds
its own per-item identifier — `productId`, `documentId`, etc. — to
its own subtree's spans) work correctly without leakage between
instances. Augmentation within the parent context (before fan-out
dispatch, or in code that runs serially) flows forward to subsequent
spans in that context, per normal context-primitive semantics.

**Backend-mapping contract.** The OTel mapping is the primary
cross-vendor propagation: §5.6 specifies the `openarmature.user.*`
cross-cutting attribute family, which appears on every span and
every OTel log record (§7) emitted during the invocation. Every
observability backend that consumes OTel spans (Phoenix / Arize,
Honeycomb, Datadog APM, HyperDX, Grafana Tempo, custom OTel
collectors, etc.) sees the metadata as standard OTel span attributes
with no per-backend wiring beyond the OTel mapping itself.

Backends whose data model carries trace-level metadata as a typed
field separate from OTel span attributes need an additional
propagation rule in their respective §-section. The Langfuse mapping
(§8.4.1 + §8.4.2) is the one such backend currently specified;
future observability backend mappings (when proposed) follow the
same pattern — they inherit §5.6 cross-cutting attributes by default
and only add their own propagation rules if the backend's data model
needs them.

**Cross-backend key portability.** Backends may impose their own
constraints on metadata key names (e.g., Langfuse's propagated
metadata limits keys to alphanumeric characters; some backends
disallow dots). Callers who wire OA to multiple observability
backends SHOULD use alphanumeric or camelCase keys (`tenantId`,
`userId`, `featureFlag`) for cross-backend portability. The OA
spec's API-boundary validation MUST at least enforce the
reserved-namespace rule above; implementations MAY expand the
rejected-key set to also catch backend-specific constraints early
(e.g., a Langfuse-aware implementation rejecting non-alphanumeric
keys at `invoke()` rather than at observer emission). When
implementations do NOT expand, backend-specific key constraints
surface at the backend's emission layer.

### observability §5.6 — cross-cutting attributes (extended)

The existing `openarmature.correlation_id` cross-cutting attribute
remains. This proposal adds a new cross-cutting attribute family:

**`openarmature.user.<key>` cross-cutting attributes.** For each
entry `(key, value)` in the caller-supplied invocation metadata (per
§3.4), the implementation MUST emit a span attribute named
`openarmature.user.<key>` with the supplied `value` on every span
emitted during the invocation. The attribute is cross-cutting in the
same sense as `openarmature.correlation_id`: it appears on the
invocation span, every node span, every subgraph span, every fan-out
instance span, every LLM provider span, and every retry attempt
span.

The `openarmature.user.` namespace is reserved for caller-supplied
metadata; the OA spec does NOT define any normative attribute names
under this prefix. Future OA-normative attributes go under
`openarmature.*` (the existing namespace) or `gen_ai.*` (when the
GenAI semconv has settled a cross-vendor name). Reserving the
`openarmature.user.` prefix gives callers a stable, collision-free
namespace they can rely on across spec versions.

**Detached trace mode (§4.4) and caller metadata.** Span attributes
emitted in detached subgraphs and detached fan-out instances also
carry the full set of `openarmature.user.*` attributes — the
metadata is invocation-scoped, not trace-scoped, so it flows through
detached children unchanged. (Matches the `openarmature.correlation_id`
behavior described in §3.1.)

**OTel log records (§7) and caller metadata.** Log records emitted
during an invocation MUST also carry the `openarmature.user.*`
attribute set, alongside the existing `openarmature.correlation_id`
on log records. Same OTel Logs Bridge mechanism as §7.

### observability §8.4 — Langfuse trace and observation propagation (extended)

This section is the Langfuse-specific instance of the per-backend
propagation pattern described in §3.4's backend-mapping contract.
Langfuse's data model treats `trace.metadata` and
`observation.metadata` as typed top-level fields separate from OTel
span attributes; the Langfuse observer must populate them
explicitly. (OTel-attribute-based backends — Phoenix, Honeycomb,
Datadog, etc. — do NOT need this per-backend propagation; they
inherit the §5.6 `openarmature.user.*` cross-cutting attributes from
the OTel observer's span emission.)

The §8.4.1 trace-level mapping (introduced by proposal 0031)
specifies how invocation-span attributes surface as Langfuse
`trace.*` fields. This proposal extends both the trace-level and
observation-level mappings with the caller-supplied metadata
propagation:

**Distinction from Langfuse Sessions.** Langfuse's `trace.metadata`
field (the target of this proposal's propagation rules) is distinct
from Langfuse's Sessions feature. Sessions group multiple traces
under a single `sessionId` for cross-invocation conversation replay;
they are deferred to proposal 0020 (sessions capability) per §8.10
of observability. This proposal's metadata is per-invocation
arbitrary key/value enrichment used for filtering and search;
metadata entries are NOT promoted to Langfuse's `userId` /
`sessionId` Trace fields by this propagation rule. The two surfaces
are complementary and orthogonal: a future invocation of OA's
sessions capability would populate `trace.sessionId` separately,
without affecting `trace.metadata`.

**Langfuse-specific constraints on caller-supplied metadata.**
Langfuse's documentation states that propagated metadata keys are
limited to alphanumeric characters and values are limited to
200-character strings. Callers wiring OA to a Langfuse backend
SHOULD use alphanumeric keys (e.g., camelCase like `tenantId`)
within Langfuse's value-length bounds. The OA API-boundary
validation does NOT enforce these constraints (they are
Langfuse-specific, not spec-wide); a key that violates Langfuse's
constraints reaches the Langfuse observer and is handled per the
Langfuse SDK's error / truncation semantics. Cross-backend
portability is the caller's concern (see §3.4 cross-backend key
portability note).

**Trace-level propagation (extends §8.4.1).** For each entry
`(key, value)` in the caller-supplied invocation metadata (per
§3.4), the Langfuse observer MUST merge the entry into the Langfuse
Trace's `metadata` map. Keys appear at the top level of
`trace.metadata` (NOT nested under a `user` sub-object), so that
Langfuse UI filtering on `metadata.<key>` matches what callers
supplied. The mapping is merged alongside the existing
`metadata.correlation_id` / `metadata.entry_node` /
`metadata.spec_version` entries (per §8.4.1).

**Observation-level propagation (extends §8.4.2).** For each entry
`(key, value)` in the caller-supplied invocation metadata, the
Langfuse observer MUST also merge the entry into EVERY Observation's
`metadata` map (every Span observation, every Generation
observation, every Event observation if used). Keys appear at the
top level of `observation.metadata`. The motivation matches §8.5's
observation-level `correlation_id` rule: observations from detached
subgraphs and detached fan-outs live in separate Traces but share
the parent invocation's caller metadata; observation-level placement
lets users filter across all of them in one Langfuse UI query
without first finding the related Traces.

**Key collision with §8.4.1 / §8.4.2 reserved keys.** Caller-supplied
keys MUST NOT use `correlation_id`, `entry_node`, `spec_version`,
`namespace`, `step`, `attempt_index`, `fan_out_index`,
`fan_out_item_count`, `fan_out_concurrency`, `fan_out_error_policy`,
`fan_out_parent_node_name`, `subgraph_name`, or
`detached_child_trace_ids`. Those keys are reserved by §8.4.1 /
§8.4.2 for OA-emitted attributes; collision would silently
overwrite OA-emitted state. The §3.4 API-boundary validation
already rejects keys under `openarmature.*` / `gen_ai.*`; the
Langfuse mapping MAY additionally reject these `metadata`-reserved
keys, OR the implementation's `invoke()` boundary MAY expand its
rejected-key set to include them. Either is acceptable as long as
the collision is rejected before observer emission.

**Detached trace mode (§4.4) and caller metadata in Langfuse.**
Detached subgraphs and detached fan-outs produce separate Langfuse
Traces; each detached Trace's `metadata` carries the same
caller-supplied entries as the parent invocation's Trace. Observers
processing detached children see the same context-propagated
mapping (per §3.4 invocation-scoped propagation).

### graph-engine §3 (clarifying touch)

The existing §3 (Invocation surface) describes `invoke()` accepting
state and an optional caller-supplied correlation ID. This proposal
adds: `invoke()` also MAY accept a caller-supplied
**invocation-metadata mapping** per observability §3.4. The
mechanism is per-language idiomatic (keyword argument; field on an
invocation-config record). The graph-engine spec does NOT prescribe
the mechanism, only that the surface is accepted at invoke time and
flows into the observability layer per §3.4.

## Conformance fixtures

Three new fixtures land at acceptance:

- **`spec/observability/conformance/026-otel-caller-supplied-metadata.{yaml,md}`** — verifies §5.6's `openarmature.user.*` cross-cutting attribute family. One case: invocation supplied with metadata `{"tenantId": "acme-corp", "productId": "xyz-123", "featureFlag": "v2-pipeline"}`; the harness asserts each `openarmature.user.<key>` attribute appears on the invocation span, on each node span, and on the LLM provider span.

- **`spec/observability/conformance/027-langfuse-caller-supplied-metadata.{yaml,md}`** — verifies §8.4.1 + §8.4.2 Langfuse propagation. Same metadata mapping; the harness asserts the entries appear on `trace.metadata` (top-level keys, sibling to `correlation_id`) AND on every Observation's `metadata` (Span observations and Generation observations).

- **`spec/observability/conformance/028-caller-metadata-namespace-rejection.{yaml,md}`** — verifies §3.4's namespace collision rejection at the API boundary. Two cases: supplying `{"openarmature.foo": "x"}` rejects at `invoke()` entry; supplying `{"gen_ai.system": "y"}` rejects at `invoke()` entry. The harness asserts no spans or Langfuse observations are produced (rejection happens before any work begins).

Harness conventions extend with one new primitive:

- `caller_metadata: {key: value, ...}` — configures the harness's
  `invoke()` call with the supplied metadata mapping. Values are
  scalars or scalar arrays per §3.4's type constraints. When the
  mapping includes a reserved-namespace key, the harness expects the
  invocation to error at boundary rather than producing spans.

## Versioning

MINOR bump. The spec's whole-spec SemVer increments to **v0.26.0** on
acceptance:

- Adds observability §3.4 (new subsection) — caller-supplied
  invocation metadata architectural contract.
- Extends observability §5.6 — `openarmature.user.*` cross-cutting
  attribute family.
- Extends observability §8.4.1 + §8.4.2 — Langfuse trace and
  observation metadata propagation rules.
- Adds graph-engine §3 clarifying note that `invoke()` accepts the
  metadata mapping.
- Adds three conformance fixtures.
- No breaking changes. Existing callers that don't supply metadata
  see no behavior change. Existing Langfuse mapping implementations
  pick up the new propagation rules at their next version bump.

CHANGELOG entry references this proposal.

## Out of scope

For this proposal specifically:

- **Per-LLM-call (not per-node) metadata override.** A caller MAY
  want to attach metadata specific to a single LLM call within a
  node (e.g., per-call cost tracking, per-call evaluation tags).
  Per-LLM-call override would require either a `metadata` argument
  on `provider.complete()` or a separate framework helper scoped to
  the next LLM call only. Not in scope; mid-invocation augmentation
  via §3.4's helper handles the broader use cases (per-node,
  per-subgraph, per-fan-out-instance), and per-LLM-call needs are
  less common.
- **Metadata-driven sampling.** Langfuse and OTel both support
  metadata-conditional sampling rules (e.g., "sample 100% of traces
  where `tenantId == 'acme-corp'`"). Sampling decisions are
  backend-side; this proposal supplies the metadata that
  backend-side rules can match on, but doesn't itself define
  sampling normativity.
- **Reserved-keyword expansion beyond OA namespaces.** Keys like
  `requestId`, `tenantId`, `userId` are caller-controlled; the
  spec does not reserve them. If the OTel GenAI semconv later
  defines a normative name for one of these, a follow-on proposal
  MAY migrate it into the `gen_ai.*` reserved set with appropriate
  migration guidance.
- **Backend-side size enforcement.** Backends (Langfuse, OTel
  exporters) have their own size limits for metadata fields. The
  spec does not constrain caller-supplied size; callers and
  backends negotiate per their respective contracts (Langfuse
  documents trace-metadata size limits; OTel SDK exporters truncate
  per their configuration).

## Open questions

None. The proposal's design choices are settled in the text above:

- **Namespace prefix on OTel** — `openarmature.user.*` (clean
  separation; reserves the prefix for caller-supplied metadata
  going forward).
- **Cross-cutting scope** — every span (invocation, node, subgraph,
  fan-out instance, LLM provider, retry attempt), matching
  `correlation_id`'s cross-cutting pattern.
- **Langfuse placement** — `trace.metadata` top-level (sibling to
  `correlation_id`) AND `observation.metadata` top-level. Top-level
  rather than nested under a `user` sub-object so Langfuse UI
  filtering on `metadata.<key>` matches caller intent.
- **API-boundary validation** — implementations MUST reject
  collisions with `openarmature.*` / `gen_ai.*` reserved namespaces
  at the `invoke()` boundary before work begins. Per-language error
  idiom per existing proposal 0030 / §6 drain-timeout precedent.
- **Detached trace propagation** — caller metadata flows through
  detached children unchanged (invocation-scoped, matches
  `correlation_id`).
- **Frozen at invoke time** — no mid-flight mutation (out-of-scope
  above).
