# 0007: Observability — OpenTelemetry Span Mapping

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-04-28
- **Accepted:**
- **Targets:** spec/observability/spec.md (creates)
- **Related:** 0001, 0003, 0004, 0006
- **Supersedes:**

## Summary

Establish the foundational behavioral specification for the OpenArmature observability capability,
beginning with a normative **OpenTelemetry span mapping**: a contract for how a graph invocation,
its subgraphs, individual node executions, and (forward-referenced) fan-out instances translate
into OTel spans, span attributes, status, and parent-child relationships. This is the first concrete
backend mapping; future proposals add Langfuse and other backends as additional sections of the
same capability spec. The mapping consumes the §6 observer event stream (graph-engine, proposal
0003) and optionally pipeline-utilities middleware (proposal 0004) to drive span lifecycle.

## Motivation

Graph-engine §6 observer hooks (proposal 0003) provide the observation primitive: every node
execution is observable by external code, with namespace, step, pre/post state, and parent-state
context. That's a substrate, not a usable observability story. Production users need their existing
OTel-based stack (Grafana, Honeycomb, DataDog, Jaeger, Tempo) to render graph runs as spans without
each user re-deriving how to map the §6 event shape onto OTel semantics.

A normative mapping has three concrete benefits:

1. **Cross-implementation parity.** A run executed by openarmature-python and the same run by
   openarmature-typescript produce equivalent OTel traces — same span hierarchy, same attribute
   names, same status mapping. Users can swap implementations without re-tooling dashboards or
   alerting rules.

2. **Backend independence.** Any OTel-compatible backend (the SDK is provider-neutral) sees a
   consistent shape. The user picks the backend; the framework's contract is the same.

3. **Foundation for Langfuse and other backends.** Once the OTel mapping is normative, Langfuse
   mapping can be specified as a sibling section that maps the same source data to Langfuse's trace
   model, with the OTel mapping providing the reference shape for cross-backend equivalence
   testing.

The work projects driving the immediate adoption (per the user's roadmap) require OTel to be
shipped before they go to production. The mapping is small enough — perhaps 200 lines of normative
text and a handful of conformance fixtures — to land in a single proposal without sprawling.

## Detailed design

The full proposed text of `spec/observability/spec.md` is reproduced below. It is written in
language-agnostic terms — Python and TypeScript map their own idioms (the OTel SDK shape is
similar across both) onto the behavioral contract described here.

The spec version under which this capability lands is determined at acceptance time and recorded in
`CHANGELOG.md`.

---

### 1. Purpose

The observability capability defines normative mappings from OpenArmature's runtime event surface
(graph-engine §6 observer events, optionally augmented by pipeline-utilities §X middleware
attribution) into well-known external observability backends. The substrate is provider-neutral; the
capability is where each concrete backend's translation lives.

This first version specifies the **OpenTelemetry** mapping. Future proposals add other backends
(Langfuse, etc.) as sibling sections of this same spec; the OTel mapping serves as the reference
shape for cross-backend equivalence.

The capability does NOT introduce new graph-engine primitives. It consumes the existing observer
event stream and middleware seam; an implementation that emits OTel spans is built on top of those,
not into the engine.

### 2. Concepts

**Span.** A unit of work in OTel — a logically distinct interval with a name, start/end timestamps,
status, attributes, and parent-child relationships. The mapping translates each user-meaningful unit
of work in a graph invocation (the invocation itself, each subgraph, each node execution, each fan-
out instance) into a span.

**Span attributes.** Key/value pairs attached to a span. OTel attribute values are restricted to
scalar types (string, int, float, bool) and arrays thereof. The mapping uses dotted-key namespaces
under the prefix `openarmature.`.

**Span status.** OTel spans carry a status of `OK`, `ERROR`, or `UNSET`. The mapping translates
graph-engine §4 error categories into status `ERROR` with a category-bearing description.

**Trace.** OTel's term for a complete tree of spans rooted at a single trace ID. One graph
invocation produces one trace.

### 3. Span hierarchy

Each invocation of the outermost graph produces the following span tree:

- **Invocation span.** Root span for the whole call. Spans the time from `invoke()` entering until
  the post-merge state is returned (or an error propagates).
- **Node spans.** One per node execution. Children of the invocation span (for outermost-graph
  nodes) or of a subgraph span (for nodes inside a subgraph) or of a fan-out instance span (for
  nodes inside a fan-out instance — see §3.3).
- **Subgraph spans.** When a `SubgraphNode` runs, a span representing the entire subgraph execution
  wraps the inner-node spans. Child of the parent's invocation or subgraph span; sibling-equivalent
  to the surrounding parent's other node spans.
- **Fan-out spans.** Once proposal 0005 lands, a fan-out node's overall execution is one span;
  each fan-out instance produces its own subgraph span as a child. Per-instance attribution uses
  the `openarmature.node.fan_out_index` attribute (§4.4).

The hierarchy is illustrated for a typical case:

```
invocation (root)
├── node: outer_in
├── subgraph: outer_sub
│   ├── node: inner_x
│   └── node: inner_y
└── node: outer_out
```

#### 3.1 Span timing

A node span's start time is the moment the engine begins dispatching the node (immediately after
the prior step's edge evaluation). Its end time is the moment the engine completes the post-merge
dispatch step — equivalently, the moment the §6 observer event would fire.

A subgraph span's start time is the moment the surrounding `SubgraphNode` begins (parent dispatch
to the subgraph). Its end time is the moment the parent's merge completes for the subgraph's
projected partial update.

The invocation span's start is the entry of `invoke()`; its end is the return.

Implementations MAY drive span lifecycle either via pipeline-utilities §X middleware (open in the
pre-`next`, close in the post-`next` — recommended) or via §6 observer events (close on event
fire; open via a separate engine hook). Driving via middleware produces strictly more accurate
durations and is RECOMMENDED. The contract for the emitted spans is identical either way.

#### 3.2 Status mapping

A span's OTel status is set as follows:

| Outcome | Status | Description |
|---|---|---|
| Node returns successfully and merge succeeds | `OK` | (omit description) |
| Node raises (graph-engine §4 `node_exception`) | `ERROR` | the §4 category identifier |
| Edge function raises (`edge_exception`) | `ERROR` | the §4 category identifier; status applied to the *preceding* node span |
| Reducer raises (`reducer_error`) | `ERROR` | the §4 category identifier |
| Routing error (`routing_error`) | `ERROR` | the §4 category identifier; status applied to the preceding node span |
| State validation error (`state_validation_error`) at exit | `ERROR` | the §4 category identifier; status applied to the invocation span |

When a span is set to `ERROR`, an OTel exception event MUST be recorded on the span carrying the
exception's class name and message; the exception's stack trace SHOULD be attached when the
language's OTel SDK supports it.

#### 3.3 Parent-child rules

Spans are parented as follows, using the §6 `namespace` and (forward-referenced) `fan_out_index`
fields:

- A node event with `namespace = [name]` and `parent_states = []` corresponds to an outermost-graph
  node. Its span's parent is the invocation span.
- A node event with `namespace = [outer_sub, inner_name]` corresponds to a node inside a subgraph.
  Its span's parent is the subgraph span for `outer_sub`.
- A node event with `namespace = [outer_sub, even_inner_sub, inner_inner_name]` corresponds to a
  node inside a doubly-nested subgraph. Its span's parent is the doubly-nested subgraph span.
- (Forward-referenced) A node event with `fan_out_index` populated corresponds to a node inside a
  fan-out instance. Its span's parent is the fan-out instance span (one per `fan_out_index` value).

The invariant `len(parent_states) == len(namespace) - 1` from §6 is preserved by this mapping: each
parent-state entry corresponds to exactly one ancestor span.

### 4. Attribute namespace

All openarmature-emitted attributes use the prefix `openarmature.`. The mapping defines the
following normative attribute keys; implementations MUST emit each on the spans listed.

#### 4.1 Invocation span attributes

- `openarmature.invocation_id` — string. A unique identifier for this invocation. Format is
  implementation-defined; UUIDv4 is RECOMMENDED.
- `openarmature.graph.entry_node` — string. The entry node name of the outermost graph.
- `openarmature.graph.spec_version` — string. The version of the openarmature-spec the
  implementation targets (e.g., `"0.7.0"`). Sourced from the implementation's package metadata.

#### 4.2 Node span attributes

Required on every node span:

- `openarmature.node.name` — string. The node's name in its immediate containing graph.
- `openarmature.node.namespace` — string array. The §6 `namespace` field, as an OTel string array.
  Implementations MUST NOT join the namespace into a single string at the OTel boundary.
- `openarmature.node.step` — int. The §6 `step` field.

When the node fails:

- `openarmature.error.category` — string. The §4 category identifier (e.g., `node_exception`,
  `reducer_error`).

#### 4.3 Subgraph span attributes

Required on every subgraph span:

- `openarmature.node.name` — string. The name of the `SubgraphNode` in the parent graph.
- `openarmature.subgraph.name` — string. The compiled subgraph's name (if the implementation tracks
  one) or the empty string. Optional in practice; populated when available.

#### 4.4 Fan-out span attributes (forward-referenced from proposal 0005)

When proposal 0005 (parallel fan-out) lands, the following attributes MUST appear on fan-out
instance spans:

- `openarmature.node.fan_out_index` — int. The §6 `fan_out_index` for this instance.
- `openarmature.fan_out.parent_node_name` — string. The fan-out node's name in the parent graph.

Fan-out node spans (the parent of the per-instance subgraph spans) carry:

- `openarmature.fan_out.item_count` — int. The number of instances run.
- `openarmature.fan_out.concurrency` — int. The configured concurrency bound (or a sentinel int
  for unbounded; 0 is RECOMMENDED).

#### 4.5 LLM provider attributes (forward-referenced from proposal 0006)

Implementations of the llm-provider capability (proposal 0006) SHOULD emit a span around each
`complete()` call. The span's attributes include:

- `openarmature.llm.model` — string. The model identifier the provider is bound to.
- `openarmature.llm.finish_reason` — string. The §6 `finish_reason` from the response.
- `openarmature.llm.usage.prompt_tokens`, `openarmature.llm.usage.completion_tokens`,
  `openarmature.llm.usage.total_tokens` — int. From the response's usage record. Omit when null.

The LLM provider span's parent is the node span (or middleware span — see §5) of the node that
invoked the provider. This provides direct attribution of LLM calls to the graph nodes they
originate from.

### 5. Driving span lifecycle

Implementations have two reasonable paths to drive span open/close:

**Middleware-driven (RECOMMENDED).** A pipeline-utilities §X middleware (proposal 0004) wraps every
node:

```
async def otel_middleware(state, next):
    with tracer.start_as_current_span(span_name(state)) as span:
        try:
            partial_update = await next(state)
            span.set_status(OK)
            return partial_update
        except Exception as exc:
            span.set_status(ERROR, description=category_of(exc))
            span.record_exception(exc)
            raise
```

Span timing matches actual node execution. Subgraph spans are similarly driven by middleware around
the `SubgraphNode` dispatch.

**Observer-event-driven.** The graph-engine §6 observer event fires once per node, post-merge, with
the full event shape. An OTel observer can emit a one-shot point span (zero duration) per event.
This loses span duration but requires no additional engine seams; useful when middleware isn't
available.

The conformance suite tests against the *emitted span structure*, not the driving mechanism;
implementations may use either approach.

### 6. Determinism

OTel span content is a function of (a) the §6 observer event stream and (b) implementation-specific
data (timestamps, span IDs, trace IDs). The graph-engine §5 determinism guarantee covers the §6
event stream — for the same input, the same events fire in the same order with the same payloads.
The implementation-specific data (IDs, timestamps) is inherently nondeterministic and is therefore
NOT covered by determinism guarantees.

The conformance suite asserts determinism over the *deterministic* portion of span content: span
hierarchy, span names, span attributes (excluding timing-derived attributes), and span status. It
does NOT assert exact timestamps or IDs.

### 7. Out of scope

Not covered by this specification; deferred to follow-on proposals or sibling sections of this
spec:

- **Langfuse mapping** — separate proposal; will live as §X of this same spec.
- **Custom backends** — users may emit any custom backend by implementing observers and middleware
  that consume the §6 stream and the spec doesn't constrain those.
- **Sampling** — OTel sampling is configured at the SDK level, outside the framework's contract.
  Implementations MAY hint via `record_exception` and span priority but the contract here is on
  the structure of emitted spans, not on whether to emit them.
- **Log correlation** — automatic injection of trace ID into the framework's structured log output.
  Useful but separable; defer to a sibling proposal.
- **Metrics** — OTel metrics (counters, histograms) for graph-level operations. The current spec
  is trace-only.
- **Baggage and context propagation** — OTel baggage for request-ID-style propagation across
  service boundaries. Defer until a concrete cross-service use case surfaces.
- **Span links** — OTel span links between traces (e.g., for batch operations that accumulate
  inputs from many traces). Defer until needed.

---

## Conformance test impact

Add a new conformance directory `spec/observability/conformance/` with the following fixtures.
Each fixture's expected output is a normalized span tree (excluding timestamps and IDs); the
conformance harness in each implementation captures emitted spans via an in-memory OTel exporter
and compares structurally.

1. **`001-otel-basic-trace`** — linear graph with three nodes. Verifies:
   - One invocation span, three node spans as children, in execution order.
   - Each node span carries `openarmature.node.name`, `openarmature.node.namespace`,
     `openarmature.node.step`.
   - Invocation span carries `openarmature.invocation_id`, `openarmature.graph.entry_node`.
   - All spans have status `OK`.

2. **`002-otel-subgraph-hierarchy`** — outer + subgraph. Verifies:
   - Hierarchy: invocation → outer_in → subgraph(outer_sub) → inner_x, inner_y → outer_out.
   - Subgraph span carries `openarmature.node.name` (the SubgraphNode's name in the parent).
   - Inner node spans' parent is the subgraph span.
   - `openarmature.node.namespace` on inner nodes is the full chain (e.g., `["outer_sub",
     "inner_x"]`).

3. **`003-otel-error-status`** — a node raises. Verifies:
   - The failing node's span has status `ERROR` with description matching the §4 category.
   - The exception is recorded on the span via `record_exception`.
   - Sibling spans (preceding the failure) have status `OK`.
   - The invocation span has status `ERROR` (the error propagates out).

4. **`004-otel-routing-error-attribution`** — a conditional edge returns an undeclared node name
   (`routing_error` per §4). Verifies:
   - The preceding node's span has status `ERROR` with description `routing_error`.
   - The routing error is recorded as an exception on the preceding node's span (no separate span
     for the edge function).

5. **`005-otel-llm-provider-span-nested`** — a node calls a mock OpenAI-compatible provider
   (proposal 0006). Verifies:
   - A child span under the node span exists for the provider call.
   - The child span carries `openarmature.llm.model`, `openarmature.llm.finish_reason`,
     `openarmature.llm.usage.*`.

6. **`006-otel-fan-out-instance-attribution`** — (depends on proposal 0005). Verifies:
   - The fan-out node has a parent span; each instance is a child subgraph span.
   - Per-instance subgraph spans carry `openarmature.node.fan_out_index` (0, 1, 2, …).
   - Inner-node spans within each instance are parented to that instance's subgraph span.

7. **`007-otel-determinism`** — same graph, two runs. Verifies the *normalized* span tree
   (excluding timestamps and IDs) is identical across runs.

The conformance harness supplies an in-memory OTel `SpanExporter` for capturing spans;
implementations register it as a `SpanProcessor` for the duration of the test. The fixtures
themselves contain no real exporter URLs.

## Alternatives considered

**Don't normalize OTel attribute names — let each implementation choose.** Path of least resistance
but loses cross-implementation parity. A user's dashboard query that filters
`openarmature.node.name = "summarize"` would need to be re-written for each implementation.
Rejected: this is exactly the multi-language consistency problem the charter exists to address.

**Use a different attribute prefix.** Rejected on grounds of clarity. `openarmature.*` is
unambiguous, matches the project name, and namespaces cleanly under the OTel attribute model.

**Match an existing OTel semantic convention namespace** (e.g., `gen_ai.*` for LLM attributes).
Rejected for v1: the OTel `gen_ai.*` SemConv is still evolving (drafts and stable releases shifting
quarterly), and tying the spec to it now risks needing PATCH-level rebases as it changes.
Implementations MAY emit `gen_ai.*` attributes IN ADDITION to `openarmature.llm.*`; the
`openarmature.*` namespace is the spec's stable contract.

**Drive span lifecycle exclusively through observer events.** Simpler — no dependency on proposal
0004 middleware. Rejected because it loses span duration accuracy (point spans only) and provides
no clean place to wrap synchronous LLM-provider calls or other within-node sub-operations.
Middleware is the right layer; the spec recommends middleware-driven and treats observer-driven as
acceptable but inferior.

**Bake span content into the engine itself (graph-engine §6 emits spans directly).** Rejected
because it forces every implementation to depend on OTel SDKs at the engine layer. The current
design keeps the engine OTel-free and the OTel mapping as an opt-in capability layered above.

**Emit one span per observer event (no parent-child structure).** Rejected — the parent-child
hierarchy IS the value. Flat span lists are dramatically less useful in trace UIs.

**Match Langfuse's hierarchy directly and treat OTel as a derived view.** Rejected because OTel is
the stricter, more widely-adopted model — defining OTel first and Langfuse as an additional
mapping (which can compose with the OTel pipeline or run alongside) is the cleaner direction.
Langfuse's own tracing model (sessions / traces / observations / spans) maps onto OTel reasonably,
not the other way around.

**Forward-reference proposals 0005 and 0006 in this spec.** The current text references both
(`fan_out_index` from 0005 in §3 and §4.4; LLM-provider attributes from 0006 in §4.5). An
alternative would defer those references until the upstream proposals accept. Currently chosen:
include as forward references with explicit "(forward-referenced from proposal NNNN)" tags. The
references are inert if 0005 / 0006 don't accept; if they do accept, the OTel mapping is already
ready. If either upstream proposal changes shape during review, the OTel reference is revised in
lockstep before this proposal's acceptance.

## Open questions

1. **Should the LLM-provider span (§4.5) be normative or informative?** Currently SHOULD. Making
   it MUST would mean every llm-provider implementation must integrate with OTel — that's a strong
   coupling. SHOULD lets implementations skip OTel entirely. Probably leave as SHOULD; revisit if
   implementations diverge.

2. **Should `openarmature.invocation_id` be UUID-required, or is "string is enough" sufficient?**
   Currently RECOMMENDED but not mandatory. Mandating UUID would simplify cross-implementation
   correlation but locks implementations into a specific format. Probably leave permissive.

3. **Span name format for nodes.** Currently spec says implementations emit a node span — but
   doesn't specify the span *name*. OTel conventions suggest a short, low-cardinality name. Two
   reasonable options: span name = node name (high cardinality if many distinct nodes), or span
   name = `openarmature.node` with node name as an attribute (low cardinality, easier to query
   in-aggregate). Currently leaning toward node name as the span name, with the namespace and
   step as attributes; revisit if cardinality concerns surface in implementation feedback.

4. **Edge evaluation spans?** Currently the spec doesn't emit a span for edge evaluation — edge
   logic is folded into the preceding node's span (status mapping §3.2 handles edge errors as
   the preceding node's failure). An alternative: emit a tiny edge span between each pair of node
   spans. Likely too noisy; defer unless real diagnostic need surfaces.

5. **Status mapping for `state_validation_error`.** Currently spec says applied to the invocation
   span. Should the failed node's span ALSO be marked ERROR (since the failure was during its
   merge step)? Currently the contract is: the engine's `node_exception` carries the state
   validation error and the node's span gets marked ERROR via §3.2. The invocation span
   inherits ERROR through normal OTel propagation. Revisit if the duplicated error reporting is
   noisy.

6. **Cross-trace correlation for fan-out.** Each fan-out instance currently runs as a child span
   of the fan-out parent within the same trace. An alternative: each instance runs as a separate
   trace linked via OTel span links (cleaner for downstream services that consume one trace per
   item). Defer until needed.
