# Observability

Canonical behavioral specification for the OpenArmature observability capability.

- **Capability:** observability
- **Introduced:** spec version 0.7.0
- **History:**
  - created by [proposal 0007](../../proposals/0007-observability-otel-span-mapping.md)

This specification is language-agnostic. Each implementation (Python, TypeScript, …) maps its own idioms
onto the behavioral contract described here. Conformance is verified by the fixtures under `conformance/`.

Normative keywords (MUST, MUST NOT, SHOULD, MAY) are used per [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

This first version of the observability capability defines two foundational concepts (cross-backend
correlation ID, OpenTelemetry span and log mapping) and one concrete backend mapping (OTel). Future
proposals add other backend mappings (e.g., Langfuse) as additional sections of this same spec.

---

## 1. Purpose

The observability capability defines normative mappings from OpenArmature's runtime event surface
(graph-engine §6 observer events, specifically the v0.6.0 started/completed event pairs) into
well-known external observability backends. The substrate is provider-neutral; the capability is
where each concrete backend's translation lives.

This first version specifies the **OpenTelemetry** mapping. Future proposals add other backends
(Langfuse, etc.) as sibling sections of this same spec; the OTel mapping serves as the reference
shape for cross-backend equivalence.

The capability does NOT introduce new graph-engine primitives. It consumes the existing observer
event stream — `started` events open spans, `completed` events close them. An implementation that
emits OTel spans is built on top of §6, not into the engine.

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
Distinct from `invocation_id` — the framework-generated `invocation_id` correlates spans within
a single backend, while `correlation_id` is application-supplied (or auto-generated when absent)
and is intended to be visible in every backend the implementation emits to. A user running an
LLM workflow with both an OTel backend (system traces, logs) and a Langfuse backend
(LLM-specific traces) uses the `correlation_id` as a join key between them: find a slow request
in Langfuse, search for its `correlation_id` in OTel logs, and see the surrounding
infrastructure activity. See §3 (architectural contract) and §5.6 (OTel attribute realization).

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
| `invocation_id` | Framework | Within-backend correlation; ties spans of one invocation together inside a single backend |

Both MAY be the same value if the user chooses (e.g., a caller-supplied UUID could be used as
both), but the spec treats them as distinct fields. Backends MUST NOT conflate them.

### 3.3 Backend-mapping contract

Each backend mapping in this spec MUST define how the correlation ID surfaces in that backend.
For the OTel mapping (this proposal):

- §5.6 specifies the `openarmature.correlation_id` span attribute that MUST appear on every
  span emitted during an invocation.
- §7 specifies the log-record correlation rules — `openarmature.correlation_id` on every log
  record emitted during an invocation, alongside OTel-native `trace_id`/`span_id`.

Future backend mappings (Langfuse, etc.) follow the same pattern: each spec section MUST
include a "correlation ID realization" subsection naming the field/attribute/metadata key the
backend uses.

**Detached trace mode** (§4.4) does not change correlation ID propagation — the correlation
ID is invocation-scoped, not trace-scoped, so it flows through detached subgraphs and fan-outs
unchanged. A detached subgraph's spans carry the same correlation ID as the parent trace's
spans.

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
keyed by `(namespace, attempt_index, fan_out_index)` and pairs each `completed` event with its
corresponding `started`. Because the §6 delivery queue is strictly serial across an invocation,
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

When a span is set to `ERROR`, an OTel exception event MUST be recorded on the span carrying the
exception's class name and message; the exception's stack trace SHOULD be attached when the
language's OTel SDK supports it.

The three `state_validation_error` rows above attribute the failure to exactly one span — the
specific span where the validation occurred. The invocation span inherits `ERROR` via standard
OTel parent-status-from-failed-children propagation when any of these fail, but the spec does
NOT explicitly mark the invocation span ERROR for the node-boundary case (the inheritance is
sufficient — explicit duplicate attribution would create noise without adding diagnostic value).

### 4.3 Parent-child rules

Spans are parented as follows, using the §6 `namespace` and `fan_out_index` fields:

- A node event with `namespace = [name]` and `parent_states = []` corresponds to an outermost-graph
  node. Its span's parent is the invocation span.
- A node event with `namespace = [outer_sub, inner_name]` corresponds to a node inside a subgraph.
  Its span's parent is the subgraph span for `outer_sub`.
- A node event with `namespace = [outer_sub, even_inner_sub, inner_inner_name]` corresponds to a
  node inside a doubly-nested subgraph. Its span's parent is the doubly-nested subgraph span.
- A node event with `fan_out_index` populated corresponds to a node inside a fan-out instance.
  Its span's parent is the fan-out instance span (one per `fan_out_index` value).
- A node event with `attempt_index > 0` corresponds to a retry attempt. Each attempt produces its
  own node span — the spans for attempts 0..N-1 are siblings sharing the same parent (typically
  the invocation span, subgraph span, or fan-out instance span depending on context).

The invariant `len(parent_states) == len(namespace) - 1` from §6 is preserved by this mapping: each
parent-state entry corresponds to exactly one ancestor span. The `attempt_index` and
`fan_out_index` fields disambiguate sibling spans at the same hierarchy level.

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

## 5. Attribute namespace

All openarmature-emitted attributes use the prefix `openarmature.`. The mapping defines the
following normative attribute keys; implementations MUST emit each on the spans listed.

### 5.1 Invocation span attributes

- `openarmature.invocation_id` — string. A unique identifier for this invocation. MUST be a
  UUIDv4 (canonical 36-character form: `xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`). Mandating the
  format gives users a consistent experience across implementations: dashboard queries, log
  searches, and cross-tool correlation all assume the same shape regardless of which language
  emitted the trace.
- `openarmature.graph.entry_node` — string. The entry node name of the outermost graph.
- `openarmature.graph.spec_version` — string. The version of the openarmature-spec the
  implementation targets (e.g., `"0.7.0"`). Sourced from the implementation's package metadata.

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

### 5.5 LLM provider attributes

Implementations of the llm-provider capability (per llm-provider §5 / proposal 0006), when paired
with an OTel observer per this mapping, MUST emit a span around each `complete()` call. This is a
cross-capability coupling: any implementation that ships both llm-provider and the OTel mapping
MUST wire them together so that LLM calls are not invisible in the OTel trace. Production
observability has no gaps by default rather than hoping the user remembered to instrument
LLM calls. The §6 TracerProvider-isolation requirement prevents this from duplicating spans with
external auto-instrumentation libraries (OpenInference, opentelemetry-instrumentation-openai,
etc.), which write to the OTel global provider while openarmature writes to its private one.

**Opt-out for external-instrumentation-only setups.** Implementations MUST support disabling
the openarmature-emitted LLM provider span — a configuration parameter on the OTel observer
(implementation-defined ergonomics; e.g., `disable_llm_spans=True`). This serves the explicit
case where the user prefers their external auto-instrumentation library as the canonical source
of LLM spans and wants openarmature to stay out of that lane. With the flag enabled, the OTel
observer skips the §5.5 span entirely; all other spans (node, subgraph, fan-out, etc.) continue
to emit normally per their respective rules.

The span's attributes include:

- `openarmature.llm.model` — string. The model identifier the provider is bound to.
- `openarmature.llm.finish_reason` — string. The llm-provider §6 `finish_reason` from the response.
- `openarmature.llm.usage.prompt_tokens`, `openarmature.llm.usage.completion_tokens`,
  `openarmature.llm.usage.total_tokens` — int. From the response's usage record. Omit when null.

The LLM provider span's parent is the node span of the node that invoked the provider. This
provides direct attribution of LLM calls to the graph nodes they originate from.

### 5.6 Cross-cutting attributes

These attributes appear on EVERY span emitted during an invocation, regardless of span type
(invocation, node, subgraph, fan-out instance, LLM provider call, retry attempt):

- `openarmature.correlation_id` — string. The correlation ID for this invocation, per §3. Set
  on every span when a correlation ID is in scope (which, per §3.1, is the entire duration of
  an invocation — so every span emitted during the invocation MUST carry it). The same
  correlation ID appears on spans within detached subgraphs and detached fan-out instances
  (per §4.4 detached mode).

The cross-cutting nature of `openarmature.correlation_id` means observability backends can
filter for "all spans related to request X" with a single attribute query, regardless of which
node, subgraph, or fan-out instance emitted the span.

## 6. Driving span lifecycle

The v0.6.0 §6 pair model gives OTel a natural lifecycle driver: register an observer with the
default phase subscription (both `started` and `completed`), and let the `started` event open the
span and the `completed` event close it.

**Observer-driven (RECOMMENDED).** An OTel observer maintains a stack of in-flight spans keyed by
`(namespace, attempt_index, fan_out_index)`. On a `started` event, it opens a new span with the
attributes from §4 and pushes it onto the stack. On the `completed` event with the matching key,
it pops the span, sets the status (per §4.2) and any error attributes, then closes the span.

```
async def otel_observer(event):
    key = (tuple(event.namespace), event.attempt_index, event.fan_out_index)
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
traces; filtering by `trace_id` finds only the logs from one specific trace.

**User-emitted logs from within nodes.** Logs emitted by user code inside a node function
participate in the same correlation rules: if the user uses the language's stdlib logger
(Python `logging`, TypeScript console/winston/pino), the OTel Logs Bridge handles attribution
transparently. If the user uses a custom logger that isn't bridged to OTel, framework
correlation is best-effort — the spec contract applies to logs that flow through the OTel
Logs SDK.

## 8. Determinism

OTel span content is a function of (a) the §6 observer event stream and (b) implementation-specific
data (timestamps, span IDs, trace IDs). The graph-engine §5 determinism guarantee covers the §6
event stream — for the same input, the same events fire in the same order with the same payloads.
The implementation-specific data (IDs, timestamps) is inherently nondeterministic and is therefore
NOT covered by determinism guarantees.

The conformance suite asserts determinism over the *deterministic* portion of span content: span
hierarchy, span names, span attributes (excluding timing-derived attributes), and span status. It
does NOT assert exact timestamps or IDs.

## 9. Out of scope

Not covered by this specification; deferred to follow-on proposals or sibling sections of this
spec:

- **Langfuse mapping** — separate proposal; will live as §X of this same spec.
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

