# Pipeline Utilities

Canonical behavioral specification for the OpenArmature pipeline-utilities capability.

- **Capability:** pipeline-utilities
- **Introduced:** spec version 0.5.0
- **History:**
  - created by [proposal 0004](../../proposals/0004-pipeline-utilities-middleware.md)
  - §9 Parallel fan-out added; §6.1 Retry middleware simplified (manual event dispatch removed in coordination with graph-engine §6's pair model) by [proposal 0005](../../proposals/0005-pipeline-utilities-parallel-fan-out.md)

This specification is language-agnostic. Each implementation (Python, TypeScript, …) maps its own idioms
onto the behavioral contract described here. Conformance is verified by the fixtures under `conformance/`.

Normative keywords (MUST, MUST NOT, SHOULD, MAY) are used per [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## 1. Purpose

The pipeline-utilities capability defines a layer of cross-cutting concerns that compose with the
graph-engine without modifying the engine. This first version specifies **middleware** — wrappers
around node execution — and two canonical middleware as concrete instances: **retry** and
**timing**. Both are mandated as part of the pipeline-utilities surface (§6) because their shape
is non-obvious enough to warrant a normative contract; other middleware-shaped concerns (logging,
resource lifecycle, circuit breakers) are implementable as middleware but are not spec-mandated.

Middleware solves the problem of code that should run around many node invocations without being
duplicated in each node's body. Retry, timing, logging, instrumentation, and resource lifecycle are
all middleware-shaped. Observer hooks (graph-engine §6) cover read-only observation of what
happened; middleware covers control over what happens.

The pipeline-utilities capability composes on top of graph-engine. It does NOT modify graph-engine
behavior — middleware sits between the engine's "node dispatch" step and the user's node function,
and is invisible to nodes that don't opt into middleware.

## 2. Concepts

**Middleware.** An async callable with the shape:

```
async def middleware(state, next) -> partial_update
```

where:

- `state` is the input state the wrapped node would have received (the engine's pre-merge state at
  the time of node dispatch).
- `next` is an async callable taking a single argument (the state to pass to the next layer or the
  original node) and returning the partial update from that layer.
- The middleware MUST return a partial update — a mapping of field names to new values, the same
  shape a node returns.

A middleware MAY:

- Call `next(state)` to invoke the wrapped chain, optionally inspecting or transforming the input
  state first (the transformed state is passed to `next`, NOT to the engine's merge step).
- Inspect, augment, or replace the returned partial update before returning it.
- Short-circuit by NOT calling `next` and returning its own partial update. The rest of the chain
  — subsequent middleware and the wrapped node — does not execute, and this middleware's own
  post-phase (code following `await next(...)`) is skipped. See "Pre-node and post-node phases"
  below for the dual-phase model that makes this possible.
- Catch exceptions raised by `next(state)` and either re-raise, transform, or recover (returning a
  partial update instead of raising).
- Call `next` more than once (e.g., retry middleware). The state passed to subsequent calls MAY be
  the original or a transformed version; the middleware decides.

A middleware MUST NOT:

- Mutate the input `state` object. The same immutability contract that applies to nodes
  (graph-engine §2 Node) applies to middleware. Pass a new state to `next` if a transformation is
  needed.
- Side-effect on engine internals (the reducer registry, edge map, etc.). Middleware operates only
  through the `state` and `next` it receives and the partial update it returns.

**Middleware chain.** An ordered sequence of middleware applied to a single node. The chain composes
outer-to-inner: the first middleware in the chain runs first, calls `next(state)` to invoke the
second, and so on, with the original node at the inner end.

For a chain `[m1, m2, m3]` wrapping node `n`, execution proceeds:

```
m1 sees state, calls next(s) ────► m2 sees state, calls next(s) ────► m3 sees state, calls next(s)
                                                                                  │
                                                                                  ▼
                                                                                 n(state) → partial_update
                                                                                  │
m1 returns partial_update ◄──── m2 returns partial_update ◄──── m3 returns partial_update
```

Each middleware's return value flows back through the previous layer's `next` call return.

**Pre-node and post-node phases.** A middleware function has two phases separated by
`await next(...)`. Code *before* `await next` is the **pre-node phase**, running on the way *into*
the chain (left-to-right in the diagram); code *after* `await next` returns is the **post-node
phase**, running on the way *out* (right-to-left). The wrapped node always runs at the innermost
point — it is never reached partway through the chain.

The two phases are tied to a single position in the chain: if `m1` is outermost, `m1`'s pre-phase
runs first AND `m1`'s post-phase runs last. Pre-order and post-order are not configured
independently. Concretely, a middleware function carries both phases:

```
async def my_middleware(state, next):
    # ── pre-node phase: runs on the way IN ──
    started_at = time.time()

    partial_update = await next(state)   # the rest of the chain (and eventually the node) runs here

    # ── post-node phase: runs on the way OUT ──
    log(f"node took {time.time() - started_at}s")
    return partial_update
```

This is the standard middleware shape used by Express, Koa, ASGI, Tower, Django middleware, and
similar frameworks.

## 3. Registration

Implementations MUST support two registration modes:

- **Per-node middleware.** Declared at the node's registration site, applied only to that node.
  The exact API is per-language (e.g., a `middleware=[m1, m2]` argument on `add_node`, or a
  decorator chain). The behavioral contract: the per-node middleware list is ordered outer-to-inner.
- **Per-graph middleware.** Declared on the graph builder, applied to every node in that graph.
  Subgraph nodes are wrapped at the parent-graph layer (per §4). Per-graph middleware lists are
  also ordered outer-to-inner.

When a node has both, **per-graph middleware composes outside per-node middleware**:

```
[per_graph_outer_to_inner...] → [per_node_outer_to_inner...] → node
```

Rationale: per-graph middleware is more general (timing, logging) and should observe the *full*
elapsed time including retries; per-node middleware is more specific and should run closest to the
node it knows about.

Implementations MAY provide additional registration scopes (e.g., per-subgraph, per-conditional-
branch); per-node and per-graph are the minimum.

## 4. Subgraph composition

Middleware does NOT cross the subgraph boundary. When a subgraph runs as a node inside a parent:

- The parent's per-graph middleware wraps the subgraph-node dispatch (i.e., the wrapper sees the
  parent's state going in and the projected partial update coming out).
- The parent's per-node middleware on the subgraph-node wraps the same dispatch, inside the
  per-graph middleware.
- The subgraph's own per-graph middleware wraps the subgraph's internal nodes. From the parent's
  perspective these are invisible — they are part of the subgraph's internal execution.
- The subgraph's per-node middleware wraps individual nodes inside the subgraph.

The four sets compose locally to each graph; there is no implicit propagation across the boundary.

Middleware locality is **strictly bidirectional**: parent middleware sees the subgraph as a single
dispatch (never individual inner nodes), and subgraph middleware sees only its own internals (never
anything in the parent). The subgraph is atomic from the parent's middleware perspective.

This is intentionally stricter than the §6 observer hook contract (graph-engine spec §6), where
parent-attached observers DO see subgraph-internal events with chained `namespace`. The asymmetry
is deliberate: read-only observation across the boundary is harmless, but read-write control across
the boundary would break encapsulation — a compiled subgraph reused in multiple parents would
behave differently in each depending on the parent's middleware set. Strict locality preserves the
property that a compiled subgraph runs identically regardless of where it's embedded.

## 5. Error semantics

Middleware sits between the engine and the node, so its error behavior must integrate with
graph-engine §4 cleanly.

**Errors raised by a node propagate through the chain.** If `n(state)` raises, the inner middleware
sees the exception via `await next(state)`. It MAY catch it (and recover by returning a partial
update, or re-raise after observing). Uncaught exceptions propagate outward through the chain to
the engine, which then handles them per graph-engine §4 (`node_exception`).

**Errors raised by middleware propagate the same way.** A middleware that raises produces a
`node_exception` per §4 (the raise originated within the node-execution portion of the engine's
loop). The exception's `__cause__` carries the original middleware exception. Middleware MAY raise
deliberately (e.g., a circuit-breaker middleware that raises after N consecutive failures); the
engine treats this identically to a node raising.

**The §6 observer event pair** for a node execution is dispatched once per *attempt* (per the §6
pair model). For nodes wrapped by middleware that re-attempts (such as retry), each attempt
produces its own started/completed pair with `attempt_index` set. The engine dispatches all events
— middleware does not dispatch directly. For nodes not wrapped by re-attempting middleware, every
attempt is a single execution that still produces a started/completed pair, with `attempt_index ==
0`.

**Recoverable state semantics** (graph-engine §4) are unchanged. If a middleware exception
ultimately propagates, the engine's `node_exception` carries the pre-merge state, identical to the
case where the node itself raised.

## 6. Canonical middleware

Implementations MUST provide two canonical middleware as part of the pipeline-utilities surface:
**retry** (§6.1) and **timing** (§6.2). These are the cross-cutting concerns whose shape is
non-obvious enough to warrant a normative contract — getting them right by hand requires alignment
with llm-provider §7 categories, careful clock semantics, or interaction with subgraph composition.
Implementations MAY provide additional middleware (logging, instrumentation, resource lifecycle,
circuit breakers); those are not spec-mandated and may differ in shape across implementations.

### 6.1 Retry

The retry middleware configuration record:

| Field | Description |
|---|---|
| `max_attempts` | Int, default `3`. Total attempts including the first call. `1` disables retry. |
| `classifier` | Predicate `(exception, state) -> bool`. Returns `true` if the exception is retryable. `state` is the pre-merge state the wrapped chain received as input on the failed attempt — i.e., the same `state` argument the middleware itself received. (There is no post-merge state on failure.) The default classifier ignores `state` and matches purely on exception category (see below); user-supplied classifiers MAY consult `state` for context-dependent retry policies. |
| `backoff` | Callable `(attempt_index) -> seconds`. `attempt_index` is 0-based. Default: exponential with full jitter, base 1s, cap 30s. |
| `on_retry` | Optional async callback `(exception, attempt_index) -> None`. Fires before each sleep. Implementations MAY use this for logging hooks. |

Behavior:

```
attempt = 0
while True:
    try:
        return await next(state)         # engine dispatches started+completed for this attempt
    except Exception as exc:
        if not classifier(exc, state) or attempt + 1 >= max_attempts:
            raise                        # terminal — engine dispatches completed-with-error
        if on_retry is not None:
            await on_retry(exc, attempt)
        await sleep(backoff(attempt))
        attempt += 1
```

**Per-attempt observer events.** Each retry attempt produces a started/completed event pair from
the engine (per graph-engine §6's pair model). Failed attempts have their `completed` event
populated with `error`; successful attempts have `post_state`. The engine dispatches all events;
retry middleware does NOT dispatch directly. Net result: 2N events for an N-attempt retry, with
`attempt_index` values `0..N-1` in order. The first 2(N-1) events are pairs ending in `error`;
the final two events are a pair ending in either `post_state` (success) or `error` (terminal
failure).

Observers that only need terminal outcomes (per-attempt completed events) MAY subscribe to
`phases={"completed"}` per the graph-engine §6 phase filter and skip the `started` deliveries
entirely.

**Default transient classifier.** The default classifier ignores its `state` argument and returns
`true` purely on exception category. Specifically, it MUST return `true` for exceptions whose
error category (per the carrying spec) is one of:

- `provider_unavailable` (llm-provider §7)
- `provider_rate_limit` (llm-provider §7)
- `provider_model_not_loaded` (llm-provider §7)
- Any exception whose carrying spec marks it transient

It MUST return `false` for:

- `provider_authentication`, `provider_invalid_model`, `provider_invalid_request`,
  `provider_invalid_response` (llm-provider §7)
- All graph-engine §2 compile errors (these will not arise at runtime, but listed for completeness)
- All graph-engine §4 errors except as carrier wrappers (a `node_exception` whose `__cause__` is a
  transient category MUST be classified as transient).

Dependency on llm-provider §7: the categories above are normative as of llm-provider §7 (spec
v0.4.0). If a §7 category is added, removed, or reclassified by a later proposal, the default
classifier MUST be updated in lock-step (a clarification PATCH).

**Cancellation signals MUST propagate.** Cancellation signals raised by the language runtime
(Python's `CancelledError`, TypeScript's `AbortError`, equivalents in other languages) MUST NOT
be classified as transient — cancellation is intentional, and retrying through it defeats the
calling context. In Python this is automatic: `CancelledError` extends `BaseException`, not
`Exception`, so the retry middleware's `except Exception` does not catch it. In TypeScript and
similar languages where cancellation is a regular `Exception` subclass, retry middleware
implementations MUST detect cancellation and re-raise it before consulting the classifier.

**Backoff with full jitter.** The default backoff is `random.uniform(0, min(cap, base * 2^attempt))`
where `base = 1.0` and `cap = 30.0`. The jitter is mandatory — fixed exponential backoff causes
synchronized retries from many concurrent callers, amplifying the rate-limit storm. Implementations
MAY provide additional named backoff strategies (constant, linear, exponential without jitter) but
MUST default to exponential-with-full-jitter.

**Partial-update inspection.** A retry middleware MUST NOT retry on a successful `next(state)` call
that returns an "error-shaped" partial update — partial updates are not exceptions, and the engine's
contract is that nodes signal failure by raising. If a node returns `{"error": "..."}` as data, that
is application data, not a retry trigger.

### 6.2 Timing

The timing middleware records wall-clock duration of the wrapped chain (including any inner
middleware time, e.g., retries) and dispatches the result to a user-supplied async callback. The
configuration record:

| Field | Description |
|---|---|
| `on_complete` | Async callback `(record) -> None`. Called once per dispatch after the chain returns or raises. |

A `TimingRecord`:

| Field | Description |
|---|---|
| `node_name` | String. The node name this middleware was attached to (captured at registration; see below). |
| `duration_ms` | Float. Milliseconds from middleware entry to chain return-or-raise, measured with a monotonic clock. |
| `outcome` | One of `"success"`, `"exception"`. |
| `exception_category` | String or `null`. When `outcome == "exception"` and the exception carries a `category` attribute (per graph-engine §4 / llm-provider §7), the category identifier; otherwise `null`. |

Behavior:

```
started_at = monotonic()
try:
    partial_update = await next(state)
    await on_complete(TimingRecord(
        node_name=<captured at registration>,
        duration_ms=(monotonic() - started_at) * 1000,
        outcome="success",
        exception_category=null,
    ))
    return partial_update
except Exception as exc:
    await on_complete(TimingRecord(
        node_name=<captured at registration>,
        duration_ms=(monotonic() - started_at) * 1000,
        outcome="exception",
        exception_category=getattr(exc, "category", null),
    ))
    raise
```

**Monotonic clock requirement.** Implementations MUST use the language's monotonic clock (Python's
`time.monotonic`, JavaScript's `performance.now`, equivalents elsewhere). Wall-clock time is
unreliable across NTP corrections and DST transitions; using it would produce negative durations
that corrupt downstream metric pipelines.

**Node-name capture.** Because the §2 middleware shape `(state, next)` does not expose node
identity at call time, the timing middleware captures `node_name` at registration. Two registration
forms MUST be supported:

- **Per-node use.** The user supplies `node_name` explicitly when constructing the middleware,
  alongside `on_complete`. The user already has the name at the call site (it's the first argument
  to `add_node`).
- **Per-graph use.** Implementations MUST provide a factory form (e.g., a `for_graph()`
  classmethod, a separate constructor, or a sentinel value) that defers binding until the engine
  attaches the middleware to each node at compile time. The engine resolves the factory once per
  registration site, producing per-node-bound middleware. The exact API is per-language; the
  behavioral contract is that per-graph timing middleware MUST receive the correct `node_name`
  in every record.

**Callback timing and error propagation.** `on_complete` fires inline before the wrapped chain's
result returns to the caller — a slow callback adds to the apparent node duration. Users SHOULD
keep the callback fast (queue work, defer I/O). Exceptions raised by `on_complete` propagate to
the engine as `node_exception` per graph-engine §4 (consistent with general middleware error
behavior). Users who want isolation MUST wrap their callback bodies in their own try/except.

**Composition with retry.** When timing wraps retry (`[timing, retry, node]`), the recorded
`duration_ms` includes all retry attempts and backoff sleeps — measuring the *total* time the
caller waited. When retry wraps timing (`[retry, timing, node]`), `on_complete` fires once per
attempt. Both compositions are valid; the user picks based on whether they want per-attempt
visibility (retry-wraps-timing) or end-to-end latency (timing-wraps-retry).

## 7. Determinism

Middleware introduces nondeterminism only when it explicitly does so:

- **Retry with jitter.** The default retry backoff uses random jitter; runs with the same input may
  produce observably different timing but identical final state on success. The graph-engine §5
  determinism guarantee is preserved (same final state, same observed node-execution order from the
  observer event stream).
- **Conditional middleware.** A middleware that branches on wall-clock time, request IDs, or
  similar nondeterministic inputs introduces nondeterminism. Implementations MAY warn at compile
  time when middleware appears to depend on non-deterministic sources; this is SHOULD, not MUST.

Middleware that is deterministic in its inputs (state, exception, attempt index) preserves graph-
engine §5 determinism end to end. The conformance suite asserts this for the canonical retry
middleware: with the random jitter swapped for a deterministic backoff, multiple runs of a
mocked-failure-then-success scenario produce identical final state and observer event sequences.

## 8. Out of scope

Not covered by this specification; deferred to follow-on proposals or capabilities:

- **Streaming outputs** — middleware that observes incremental partial updates from a single node.
- **Checkpointing and resume** — durable state across runs.
- **Per-pipeline rate limiting** — composable rate limiters across nodes / models / prompts.
- **Resource lifecycle** — per-stage resource loading. Implementable as middleware today; a
  canonical helper is deferred.
- **Circuit breakers** — composable failure detection across calls. Implementable as middleware
  today; a canonical helper is deferred.
- **Deadline propagation** — per-call timeouts that compose with retries.
- **Middleware on conditional edges** — wrapping the edge function. Edges are simpler (no merge
  step, no partial update); a follow-on proposal can extend middleware shape to edges if needed.
- **Per-conditional-branch middleware** — middleware that applies only to nodes routed-to from
  a specific conditional edge. Workarounds (state markers + per-node middleware) cover the
  uncommon diamond-topology case; revisit if real workflows surface that the workarounds don't
  cover.

## 9. Parallel fan-out

A **fan-out node** is a special node type that executes a compiled subgraph (or async callable)
once per item in a designated parent state field, with instances running concurrently up to a
configurable bound, and collects per-instance results back into a parent collection field.

Fan-out nodes are the single place in the engine where multiple subgraph executions overlap in time
within a single invocation; everywhere else (graph-engine §3) execution is single-threaded.

### Configuration

A fan-out node is registered with the following fields:

| Field | Description |
|---|---|
| `name` | The fan-out node's name in the parent graph. |
| `subgraph` | A compiled subgraph or async callable executed once per item. |
| `items_field` | Optional. A field name on the parent state. Its value at fan-out entry MUST be a list-typed value. The instance count is `len(items_field_value)`; each item is projected per-instance via `item_field`. Mutually exclusive with `count`. |
| `item_field` | A field name on the subgraph state to which each item is assigned at instance entry. Required when `items_field` is specified; MUST be absent when `count` is specified. |
| `count` | Optional. The instance count when no per-item data is being iterated. Accepts either a literal `int` (static count fixed at compile time) OR a callable `(state) -> int` (count read from / computed over parent state at fan-out entry). Mutually exclusive with `items_field`. |
| `collect_field` | A field name on the subgraph state whose final value is collected from each instance. |
| `target_field` | A field name on the parent state into which the collected list is merged. |
| `concurrency` | Optional. Upper bound on concurrently-running instances. Accepts either a literal `int` (static, fixed at compile time), a callable `(state) -> int` (read from / computed over parent state at fan-out entry), or `None` (unbounded). Default: `10`. Same int-or-callable shape as `count` for symmetry. |
| `error_policy` | One of `"fail_fast"` (default) or `"collect"`. See §9.5 below. |
| `on_empty` | One of `"raise"` (default) or `"noop"`. Behavior when the resolved instance count is zero. `"raise"` (default) treats empty as unexpected and raises a `node_exception` per graph-engine §4 with category `fan_out_empty`. `"noop"` treats empty as a legitimate state and produces a silent no-op (zero instances run, downstream proceeds). See §9.1 below. |
| `count_field` | Optional. A field name on the parent state into which the fan-out writes the resolved instance count after execution. MUST be a declared int-typed field on the parent state schema. Useful for programmatic inspection of how many instances ran (e.g., a downstream conditional edge that branches on `state.count_field == 0`). Written at the fan-in step regardless of `on_empty` mode; if `on_empty: "raise"` and count is zero, the raise occurs before the field is written, so the prior value is preserved. |
| `inputs` | Optional `Mapping[str, str]` (subgraph_field → parent_field) to copy additional non-per-item parent fields into each instance. Same semantics as graph-engine §2 explicit input mapping. |
| `extra_outputs` | Optional `Mapping[str, str]` (parent_field → subgraph_field) to merge additional non-collected fields back from each instance via the parent's reducer. |
| `instance_middleware` | Optional ordered list of middleware that wrap each instance's invocation as a unit. Composes outer-to-inner. Sits *between* outer fan-out-node-level middleware (per-graph + per-node on the fan-out node itself) and the inner subgraph's own middleware. See §9.7 below. |

All `*_field` references (whether mandatory in their mode or optional `inputs`/`extra_outputs`
entries) MUST refer to declared fields on the relevant state schema; compilation MUST fail with
category `mapping_references_undeclared_field` (graph-engine §2) otherwise. Mode-specific
validation:

- **`items_field` mode** — `items_field` MUST be declared as a list-typed field; `item_field`
  MUST be specified. If `items_field` is not list-typed, compilation MUST fail with a new
  category `fan_out_field_not_list`.
- **`count` mode** — `count` MUST be either a literal int OR a callable; `item_field` MUST be
  absent. If `count` is a callable, implementations SHOULD validate at compile time that the
  return type is `int` (per the language's type system).
- **Mutual exclusion** — exactly one of `items_field` or `count` MUST be specified. If both or
  neither are specified, compilation MUST fail with a new category
  `fan_out_count_mode_ambiguous`.
- **`on_empty`** — MUST be one of `"raise"` or `"noop"`. Other values are a compile error.
- **`count_field`** — if specified, MUST refer to a declared int-typed field on the parent state
  schema. Type mismatch is a compile error per the existing `mapping_references_undeclared_field`
  rule applied symmetrically to type compatibility.

### 9.1 Per-instance projection

At fan-out entry, the engine snapshots the parent state and resolves the instance count and
per-instance state per the active mode:

**`items_field` mode.** For each item in the snapshot's `items_field`, an instance is constructed
with:

- `item_field` ← the item value
- For each `(subgraph_field, parent_field)` in `inputs`: subgraph field ← parent field's value at
  the snapshot
- All other subgraph fields ← schema defaults

Per-item items are assigned in input list order. Each instance is tagged internally with its
0-based index in the input list (`fan_out_index`); see graph-engine §6 below.

**`count` mode.** The engine evaluates `count` against the snapshot:

- If `count` is a literal int, that value is used directly.
- If `count` is a callable, the engine invokes `count(snapshot)`; the returned int is used. The
  callable MUST NOT mutate `snapshot`. The returned value MUST be a non-negative integer;
  negative values raise a runtime `node_exception` per §4 with category
  `fan_out_invalid_count`.

`count` instances are then constructed with:

- For each `(subgraph_field, parent_field)` in `inputs`: subgraph field ← parent field's value at
  the snapshot
- All other subgraph fields ← schema defaults
- (No `item_field` projection — there are no per-item values.)

Each instance is tagged internally with its 0-based index (`fan_out_index`), `0..count-1`. The
inner subgraph cannot read its own `fan_out_index` directly; if the application needs the index
inside the subgraph, the user wires it through `inputs` (e.g., have the parent state carry an
indices list and pass it via `inputs`, or use a custom `count` callable that increments a
state-tracked counter).

In both modes, the instance receives a fresh subgraph state instance, NOT a shared one. Mutations
within an instance do not affect siblings.

**Empty fan-out behavior** (resolved instance count == 0, whether from `items_field == []` or
`count == 0` / a callable returning `0`) depends on the `on_empty` config:

- **`on_empty: "raise"` (default)** — the engine raises a `node_exception` per graph-engine §4
  with category `fan_out_empty`. The exception carries the pre-fan-out parent state as
  `recoverable_state`. The fan-out's `started` event still fires (the engine fires it before
  resolving the count), but no `completed` event fires; the propagated `node_exception` takes
  the place of the completed event. This is the safe default — empty inputs are usually
  unexpected and silent skipping is a footgun; raising surfaces the situation immediately.
- **`on_empty: "noop"`** — the fan-out runs zero instances and produces a clean no-op. The
  fan-in step contributes empty lists to `target_field` and `errors_field` (if configured),
  which under the `append` reducer leaves both fields unchanged from their pre-fan-out values.
  If `count_field` is configured, it is written with `0`. The fan-out node fires its full §6
  event pair: a `started` event with `pre_state` populated, then a `completed` event with
  `pre_state` and `post_state` both populated and identical for the fan-out's output fields.
  Downstream execution proceeds normally.

`fan_out_empty` is not a transient category — retrying the fan-out with the same inputs will
produce the same empty count. Retry middleware (§6.1) MUST NOT classify it as transient.

When `on_empty: "noop"` is used and the user wants to react to the empty case, the recommended
pattern is to configure `count_field` and add a downstream conditional edge that branches on the
field value:

```python
add_fan_out_node(
    name="process",
    subgraph=worker,
    items_field="items",
    item_field="item",
    collect_field="result",
    target_field="results",
    on_empty="noop",
    count_field="processed_count",
)

builder.add_conditional_edge(
    "process",
    lambda s: "halt_on_empty" if s.processed_count == 0 else "continue",
)
```

Empty inputs ARE legitimate in some LLM pipeline shapes (a retrieval node that genuinely might
return no documents, an upstream filter that may reject every candidate, a queue that may be
drained). For those cases, set `on_empty: "noop"` explicitly. The default raises so that empty
inputs that weren't anticipated surface loudly rather than disappear silently.

### 9.2 Concurrent execution

The engine resolves `concurrency` against the parent state snapshot at fan-out entry, using the
same int-or-callable rules as `count` (§9.1):

- If `concurrency` is a literal int, that value is used directly.
- If `concurrency` is a callable, the engine invokes `concurrency(snapshot)` once at entry; the
  returned int is used. The callable MUST NOT mutate `snapshot`. The returned value MUST be a
  positive integer or `None` (unbounded); zero or negative values raise a runtime
  `node_exception` with category `fan_out_invalid_concurrency`.
- `None` (literal or returned from a callable) means unbounded — every instance runs in parallel.

Up to the resolved `concurrency` instances execute concurrently. The order in which instances
*start* MUST match instance-index order (input list order in `items_field` mode; `0..count-1` in
`count` mode); the order in which they *complete* depends on per-instance work. Implementations
MUST use the language's idiomatic async concurrency primitive (Python: `asyncio.TaskGroup` or
`asyncio.Semaphore` + `asyncio.gather`; TypeScript: `Promise.all` with a semaphore wrapper) and
MUST NOT block one instance's progress on another's.

Concurrency is resolved exactly once at fan-out entry — the limit does not change mid-execution
even if the parent state changes (which it can't, since the parent doesn't step during fan-out
per graph-engine §3). When `concurrency` is a callable, the callable's determinism is the user's
responsibility — the framework cannot statically or dynamically detect nondeterministic
callables (same model as node implementations per graph-engine §5). For the §5 determinism
guarantee to apply to a graph using a callable `concurrency`, the callable MUST be a pure
function of its `state` argument. Callables that consult wall-clock time, randomness, or other
nondeterministic sources are permitted, but graph runs using them fall under the §5
nondeterministic-user-code carve-out.

### 9.3 Per-instance fan-in

When an instance completes, the engine extracts:

- `collect_field`'s final value → contributed to the parent's `target_field`
- For each `(parent_field, subgraph_field)` in `extra_outputs`: subgraph field's final value →
  contributed to the parent's named field

Instance contributions are NOT merged into the parent state until ALL instances complete. The
fan-in step then merges all per-instance contributions into the parent state in instance-index
order via the parent's reducer for the named field. The reducer for `target_field` MUST be a
list-extending reducer (`append` or a user-defined equivalent that concatenates list values);
the reducer for any field named in `extra_outputs` MUST accept the value type the subgraph
produces.

The collected list at `target_field` preserves instance-index order (instance 0's value, then
instance 1's, …), independent of completion order. In `items_field` mode, instance index ==
input list index, so this is also input list order. In `count` mode, instance indices run
`0..count-1`.

### 9.4 Item ordering and fan-in determinism

A fan-out node MUST produce the same final state on identical input regardless of per-instance
completion order, given deterministic instance work. The collected `target_field` value is in
instance-index order; `extra_outputs` merges happen via the parent's reducer in instance-index
order. This preserves graph-engine §5 determinism end to end.

In `count` mode where `count` is a callable, the callable's determinism is the user's
responsibility — the framework cannot statically or dynamically detect nondeterministic
callables (same model as node implementations per graph-engine §5). For the §5 determinism
guarantee to apply to a graph using a callable `count`, the callable MUST be a pure function of
its `state` argument. Callables that consult wall-clock time, randomness, or other
nondeterministic sources are permitted, but graph runs using them fall under the §5
nondeterministic-user-code carve-out.

### 9.5 Error policy

`error_policy: "fail_fast"` (default):

- The first instance that raises causes the engine to cancel all sibling instances and propagate
  the original exception. Cancellation MUST be cooperative (the language's idiomatic cancellation
  signal: Python `CancelledError`, TypeScript `AbortSignal`); instances MUST be given the
  opportunity to clean up.
- The propagated exception is the offending instance's, wrapped in a `node_exception` per
  graph-engine §4. Recoverable state is the parent state at fan-out entry (the snapshot).
- Sibling cancellations DO NOT produce additional `node_exception` per cancelled instance;
  cancellations are infrastructure, not user-visible errors. Observers MAY see partial events
  from cancelled instances (whatever fired before cancellation propagated).

`error_policy: "collect"`:

- All instances run to completion (whether success or error).
- A successful instance contributes to fan-in normally.
- A failed instance contributes nothing to `target_field` (its slot is OMITTED — input order is
  preserved among successes).
- After all instances complete, fan-in merges successes; the engine then proceeds to the
  outgoing edge.
- Per-instance errors are recorded in a parent state field named by an additional config field
  `errors_field` (default: omitted, meaning errors are silently dropped after their per-instance
  events fire). `errors_field` MUST refer to a declared list-typed field with an extending
  reducer.

The `collect` policy never raises from the fan-out node itself; no exception is propagated even
if ALL instances fail. Users who need failure thresholds compose this with downstream conditional
edges over the `errors_field`.

### 9.6 Composition with middleware

Per-graph and per-node middleware (§3) compose with fan-out as follows:

- **Per-graph middleware** wraps the fan-out node *as a single dispatch* — sees the input parent
  state, sees the merged-fan-in partial update on completion. Per-graph middleware does NOT see
  per-instance state.
- **Per-node middleware on the fan-out node itself** wraps the same dispatch; same scope as
  per-graph but applied only to this fan-out.
- **Per-node middleware on the inner subgraph's nodes** wraps each per-instance node call. Retry
  middleware on an inner node retries within that instance only; sibling instances are not
  retried.
- **Instance middleware** (`instance_middleware` config) wraps each instance's invocation *as a
  unit*. See §9.7 below for the precise semantics.

The composition layering, from outermost to innermost for an event flowing through the fan-out:

```
parent per-graph middleware    (outer graph; wraps fan-out as one dispatch)
└─ per-node middleware on fan-out node    (same scope, inside per-graph)
   └─ fan-out node iterates instances; for each instance:
      └─ instance_middleware    (wraps this instance's subgraph invoke as a unit)
         └─ subgraph's per-graph middleware    (wraps each inner node)
            └─ per-node middleware on inner-subgraph nodes    (per inner node)
               └─ inner node
```

This locality matches §6 observer hook composition (graph-engine spec §6) and §4 middleware
subgraph composition (this spec).

### 9.7 Instance middleware

`instance_middleware` is an ordered list of middleware applied to each instance's subgraph
invocation. It is fan-out-specific — neither a per-node nor per-graph middleware mode. The
fan-out node iterates instances, and for each instance constructs the chain:

```
instance_middleware[0] → instance_middleware[1] → … → subgraph.invoke(initial_state)
```

`subgraph.invoke(initial_state)` is the wrapped target. Each middleware sees the per-instance
initial state (built per §9.1 from the per-item projection plus any `inputs`) and returns the
subgraph's projected partial update (per §9.3). Middleware that retries by calling `next` again
re-runs the entire subgraph invocation from scratch — fresh subgraph state, fresh inner-node
execution.

Each instance gets its own independent middleware chain — no shared mutable state across
instances. Instance middleware sees the per-instance namespace (and `fan_out_index`); per-attempt
observer events from retry middleware inside `instance_middleware` carry both `attempt_index`
(per §6.1) and `fan_out_index` populated.

**Composition with `error_policy`:**

- Under `fail_fast`, when one instance's `instance_middleware` chain ultimately raises, the
  fan-out cancels siblings — including any in-flight retries inside their own
  `instance_middleware`. Retry middleware MUST honor the cancellation per the §6.1 cancellation
  rule and MUST NOT classify the cancellation signal as transient.
- Under `collect`, an instance whose `instance_middleware` chain raises (after exhausting retries
  or any other middleware short-circuit) is recorded in `errors_field` with the final exception;
  the fan-out continues with siblings.

**Composition with the fan-out node's other middleware:**

- Per-graph and per-node middleware on the fan-out node see the WHOLE fan-out as one dispatch —
  one outermost middleware enter and one outermost middleware exit per fan-out execution. They
  do NOT see per-instance retries or per-instance failures (those are absorbed by
  `instance_middleware` if present).
- This means a per-graph timing middleware on the outer graph, with an `instance_middleware`
  retry around each instance, records *total elapsed time including all per-instance retries*. A
  per-graph timing middleware sees only the fan-out as a whole; per-instance attempts are
  invisible at that scope.

The `instance_middleware` chain MUST be the same for every instance in a single fan-out — there
is no per-item middleware variation. Heterogeneous per-item behavior remains out of scope (see
§8 Out of scope for the deferred-feature list at the capability level).

## 10. Checkpointing

### 10.1 Checkpointer protocol

Implementations MUST define a Checkpointer abstraction with four operations:

- `save(invocation_id: str, record: CheckpointRecord) -> None` — persist a checkpoint record
  for the given invocation. After return, the record MUST be durable across process crashes
  for backends that document durability (in-memory backends are NOT durable and MUST document
  this). Default behavior is **synchronous** — `save` returns only after persistence succeeds.
- `load(invocation_id: str) -> CheckpointRecord | None` — return the most recent record for
  this invocation, or `None` if no record exists. The returned record MUST be structurally
  identical to what `save` last wrote for this invocation_id (round-trip integrity).
- `list(filter: CheckpointFilter | None = None) -> Iterable[CheckpointSummary]` —
  enumerate saved invocations. The summary shape includes at minimum `invocation_id`,
  `correlation_id`, `last_saved_at`, and `completed_node_count`. The `filter` shape is
  implementation-defined (per-language ergonomic API: query record matching by date range,
  correlation_id, completion status, etc.).
- `delete(invocation_id: str) -> None` — remove all records for the given invocation.
  Implementations MUST tolerate `delete` on a non-existent invocation_id (no-op, no error).

The protocol leaves serialization to the backend. The `CheckpointRecord` is an in-memory typed
object the engine hands to `save`; backends MAY pickle, JSON-encode, protobuf-serialize, or
keep references to live objects (in-memory backends). Each backend's documentation MUST state
which state shapes it supports — e.g., "JSON-native types only," "anything pickleable," "any
shape supported by Temporal's data converter."

### 10.1.1 Registration and default behavior

Checkpointing is **opt-in via registration**. A user attaches a Checkpointer to a graph at
build time (per-language ergonomic API: a `with_checkpointer(...)` builder method, a
constructor parameter, etc., matching the pattern used for §6 observer registration). Without
a registered Checkpointer:

- The engine does NOT call `save()` at any point. No `CheckpointRecord` is produced; no
  storage cost is paid; no save-related events fire on the §6 observer stream.
- `invoke(resume_invocation=X)` raises a runtime error with category `checkpoint_not_found`,
  because there is no Checkpointer to ask. (A user attempting to resume against an
  unregistered backend has misconfigured the run; the error surfaces it cleanly.)

The default-off behavior matches the dev-loop case (short runs, no need to persist anything)
and the case where checkpointing's idempotency contract (§10.5) cannot be honored. Production
batch pipelines opt in; ad-hoc and test runs do not. This mirrors §6 observer registration
and the broader OA pattern of "the contract is normative; the activation is an explicit
choice."

A graph MAY have at most one registered Checkpointer. Multiple Checkpointers (e.g., a primary
SQLite store and a secondary backup) are out of scope; users wanting that pattern can wrap
two underlying Checkpointers behind a custom protocol-conforming implementation that
fans out to both.

### 10.2 Checkpoint record shape

The `CheckpointRecord` carries:

- `invocation_id` — string. Per graph-engine v0.6.0 / observability §5.1; framework-generated
  UUIDv4 at invocation start.
- `correlation_id` — string. Per observability §3; caller-supplied or framework-generated;
  flows unchanged across resume (a resumed invocation keeps the original `correlation_id`,
  which is invocation-scoped).
- `state` — the post-merge outermost state at the latest save point. Type is the user's
  declared outermost state schema (graph-engine §1).
- `completed_positions` — ordered sequence of `NodePosition` records, one per completed node
  attempt that has been merged. Each position carries `namespace` (per graph-engine §6),
  `node_name`, `step` (monotonic across the invocation, including subgraph-internal nodes),
  `attempt_index`, and `fan_out_index` (when present).
- `fan_out_progress` — reserved field for the v2 per-instance fan-out resume follow-on
  proposal. In v1 of this section, the engine does not save inside fan-out instances at all
  (see §10.3, §10.7), so this field is absent. The field is reserved in the record shape
  so that v2 can populate it without a record-shape migration.
- `parent_states` — when the latest save point is inside a subgraph or fan-out instance, the
  ordered sequence of containing-graph states (outermost first). Per graph-engine §6
  semantics; preserved across resume so the engine can re-enter the subgraph correctly.
- `last_saved_at` — timestamp. Implementation-defined precision; SHOULD be monotonic per
  invocation (later saves have later timestamps).
- `schema_version` — string. Implementation-defined; lets backends evolve the record shape
  without breaking older saved records.

### 10.3 Save granularity — every `completed` event

The engine fires a save at every graph-engine §6 `completed` event from the following sources:

- **Outermost-graph nodes.** One save per node attempt that finishes (successful merge or
  failure captured).
- **Subgraph-internal nodes.** One save per inner-node completion, with `parent_states`
  populated per §10.2. Resume can re-enter the subgraph at any boundary; long-running
  subgraphs benefit directly from per-inner-node save granularity.
- **Fan-out node itself** (the parent dispatch node, per pipeline-utilities §9). One save when
  the fan-out as a whole has finished and its results have merged back into outer state.

The engine **does NOT save** during fan-out instance execution in v1. Fan-out instance
internal `completed` events still emit observer events (per graph-engine §6) so the
observability mapping can surface them as spans, but no checkpoint save fires for them.
Rationale: §10.7 mandates atomic-restart fan-out resume in v1 — a crash mid-fan-out causes
the entire fan-out to re-run on resume. Saving inner-instance state that the engine cannot
resume from is dead weight; eliding those saves keeps the volume bounded for high-instance-
count fan-outs. The v2 per-instance fan-out resume follow-on proposal reverses this and
introduces fan-out internal saves with configurable backend batching.

The engine calls `Checkpointer.save(invocation_id, current_record)` with the record
reflecting state immediately after the triggering event. Save is **synchronous** (the engine
awaits `save` before continuing to the next node) so that a crash immediately after a
`completed` event cannot have lost the corresponding save.

### 10.3.1 Storage and cost characteristics

A successful run of an N-node graph produces N writes against the Checkpointer. Each write
is a **full state snapshot** (not a delta), so total cost scales as `N × state_size`. The
protocol's `load(invocation_id)` returns "the most recent record" — backends are free to
implement this as upsert (one row per invocation_id, overwritten N times) or as insert-only
with timestamp-ordered reads. Most backends will choose upsert for resume-only use; the
`list()` operation determines what history is retained for inspection.

For typical LLM pipelines (state in kilobytes, dozens to hundreds of nodes) this is sub-
millisecond per save and effectively invisible. For pipelines whose state is large
(megabyte-scale outer state with many records) AND whose nodes are cheap, the per-save cost
can dominate. Backends MAY mitigate via differential storage, compression, or batched flush;
those are implementation concerns, not protocol concerns. The protocol's behavioral contract
remains "what `load` returns after a `save` completes is what was saved." Backends that
batch internally MUST flush before `save` returns to honor this; backends that defer
flushing across `save` calls accept the risk of losing the last buffered records on crash
and MUST document that risk.

### 10.4 Resume model — `invoke(resume_invocation=invocation_id)`

To resume, the application calls `invoke(...)` with a `resume_invocation` parameter naming a prior
`invocation_id`. The engine:

1. Calls `Checkpointer.load(resume_invocation)`. If `None` is returned, the engine raises a
   resume-failure error (canonical category `checkpoint_not_found`). If non-None, proceed.
2. Restores the loaded `state` as the post-merge state at the latest save point.
3. Restores the `correlation_id` from the loaded record (a resumed invocation keeps its
   original `correlation_id`; cross-backend pivots remain valid).
4. Generates a new `invocation_id` for the resumed run. **Resume produces a new invocation
   per execution attempt, not a continuation of the original invocation_id.** Rationale: each
   attempt at completing the graph is its own invocation in the observability and audit
   sense; the `correlation_id` provides the cross-attempt join key.
5. Determines the resume entry point by inspecting `completed_positions`: the engine resumes
   from the first node in graph topological order whose position is not in
   `completed_positions`. Subgraph re-entry uses `parent_states` to reconstruct the subgraph
   stack.
6. Runs from that entry point to graph termination, dispatching `started`/`completed` events
   normally for the resumed nodes, with `attempt_index` reset to 0 (per §10.6).

The state-restore-not-event-replay choice is deliberate. OA's reducer/partial-update model
(graph-engine §1) makes state at any node boundary equivalent to "all prior nodes' merged
contributions" — there is no need to replay events to reconstruct it. Event-replay (the
Temporal model) is required when nodes are not deterministic and must consult their
journaled past results; OA's graph-engine §5 already mandates determinism for the same input,
so state-restore is sufficient.

### 10.5 Idempotency contract

Nodes MUST be idempotent under re-execution. A crash mid-node (between a node's `started`
event and its `completed` event) leaves the node's external side effects in an unknown state;
on resume, the engine re-runs that node from its start. Nodes that perform non-idempotent
external operations (POST to a payment API, send an email) MUST guard those operations with
the user's own idempotency mechanism (idempotency keys, conditional database writes, output-
existence checks at the node body's entry).

This matches both reference patterns cited above: stages are idempotent under re-execution
because output-file presence (content-addressable-output reference) or checkpoint-file
presence (state-snapshot reference) blocks duplicated work. OA does not enforce idempotency
— it documents the contract.

**When a user cannot make a node idempotent.** Some operations have no clean idempotency
mechanism — for example, a third-party API that is non-idempotent and offers no
idempotency-key parameter, or an operation whose external system cannot be queried for
"already-done" state. Three options, in order of preference:

1. **Make the node idempotent at the application level.** This is the recommended path. The
   most common patterns are idempotency keys (a per-attempt unique key the external system
   uses to deduplicate), conditional writes (insert only if not exists; UPSERT with WHERE
   clauses), or output-existence checks at the node body's entry (skip the work if its
   effect is already visible). These guards make re-execution safe without spec changes.
2. **Wrap the node in middleware that records an "already-ran" sentinel in state and skips
   re-execution on resume.** Buildable on top of pipeline-utilities §6 middleware. The
   middleware checks for the sentinel on entry; if present, returns the empty partial update
   (no-op); if absent, runs the node and writes the sentinel as part of the partial update.
   Resume sees the sentinel in restored state and skips re-execution. Trade-off: the node's
   contribution to outer state is whatever the original run produced — nothing new is
   computed on resume — so this works only when the node's effect is purely external (e.g.,
   "send email" — fire-and-forget) or when the original effect on state is already captured.
3. **Don't register a Checkpointer for the graph.** Loses resume entirely; non-idempotent
   nodes are never subject to re-execution by the framework because crashes have no recovery
   path. Acceptable for non-critical workloads where re-running the whole pipeline is
   cheaper than building idempotency into the node.

A per-node `force_rerun_on_resume` opt-out is NOT specified in this section. If real
workloads demonstrate the need, a follow-on proposal can add it; for now, options 1-3 are
sufficient.

### 10.6 Retry on resume — `attempt_index` resets

When a node is resumed (i.e., it had a `started` but not a `completed` event in the saved
record, or it had not yet started), its `attempt_index` resets to `0`. Retry budgets configured
on the wrapped node (per pipeline-utilities §6.1) restart fresh on resume.

Rationale: retry budgets exist to bound transient-failure recovery during a single execution
attempt. A resumed invocation is a new execution attempt; the user's intent in resuming is
generally "give it a fresh chance," not "honor whatever attempts the prior process used up."
Persisting `attempt_index` across resume would surprise users whose retry budget got exhausted
in the prior process and now find that resume can't recover from a single transient failure.

This is consistent with §10.4's choice to mint a new `invocation_id` for the resumed run:
each resume is a fresh invocation in the observability sense, with its own retry budget.

### 10.7 Fan-out resume — atomic in v1

When a fan-out is in flight at crash time (some instances completed and merged into outer
state; some in-flight; some not yet started), v1 resume re-runs the **entire fan-out** from
scratch. The fan-out node's `completed_positions` entry is absent until all instances have
completed and merged; on resume, the engine sees the fan-out as not-yet-completed and
restarts it.

This couples directly to §10.3's "no fan-out internal saves in v1" rule: the engine never
records partial-fan-out progress because it cannot make use of that progress on resume. The
fan-out node either has its `completed_positions` entry (whole fan-out finished) or does not
(whole fan-out re-runs). There is no intermediate state.

The cost: instances whose work already completed and merged to `state` get re-run. For
fan-outs whose inner work is expensive (LLM calls, API requests), this is undesirable. A
follow-on proposal will add **per-instance fan-out resume**,
where the engine saves at fan-out instance internal `completed` events, populates
`fan_out_progress`, and consults that field on resume to skip already-completed instances.
The follow-on also introduces configurable backend batching for fan-out internal saves
(scoped to keep the volume manageable when instance counts and inner-node counts get
large). v1 keeps the spec scope-bound and ships the simpler atomic-restart contract first.

### 10.8 Composition with §6 observer hooks

`Checkpointer.save` calls SHOULD emit a graph-engine §6-style observer event so the
observability mapping (per OTel mapping §6) can surface checkpoint saves as spans. The exact
event shape — name, attributes — is left to the implementation; a span like
`openarmature.checkpoint.save` with attributes for `invocation_id`, `last_saved_at`, and
backend identifier is the recommended shape.

This is `SHOULD` rather than `MUST` because not all backends will want the observability
overhead — a high-throughput in-memory checkpointer issuing 10K+ events per second per
invocation would dwarf the actual graph events. Backends MAY suppress event emission via
configuration; users choosing to do so accept the loss of save-point visibility in their
trace UI.

### 10.9 Composition with detached trace mode (observability §4.4)

Detached trace mode (observability §4.4) and checkpoint scope are **independent**. Detached
trace mode is purely about trace UI organization — fragmenting the OTel span tree of a single
invocation into multiple traces for backend display. Checkpoint scope is about execution
recovery — what unit of work resumes as a unit.

A single `invoke()` call produces exactly one Checkpointer record set keyed by one
`invocation_id`, regardless of how many detached traces its execution produced. The
`CheckpointRecord` captures whatever state and progress exists at save time; resume is
unified at the top-level invocation. A user who configured a fan-out as detached for trace-
visualization reasons does not gain or lose any per-instance resume granularity from that
configuration — that is a fan-out resume question (§10.7), not a detached-trace question.

### 10.10 Errors

New canonical runtime category: `checkpoint_not_found` — raised when `invoke(resume_invocation=X)`
is called and `Checkpointer.load(X)` returns `None`. Non-transient (no auto-recovery via
retry — the checkpoint genuinely does not exist).

New canonical runtime category: `checkpoint_save_failed` — raised when `Checkpointer.save`
itself raises during a `completed` event handler. The behavior of the engine on save failure
is implementation-defined: implementations MAY treat save failure as a transient that bubbles
up via standard middleware (allowing user retry middleware to reattempt), or MAY raise to the
caller of `invoke()` immediately. Implementations MUST document their choice.

New canonical runtime category: `checkpoint_record_invalid` — raised when
`Checkpointer.load(X)` returns a record whose schema is incompatible with the current graph
(state shape mismatch, missing required fields, incompatible `schema_version`). Non-
transient.

### 10.11 Reference implementations and backend layering

The proposal mandates the protocol; sibling-package adapters are NOT specified normatively.
Implementations are expected to ship the protocol plus at least the minimal in-core
implementations described below. Reference adapters for durable-execution platforms
(Temporal, DBOS, Restate) ship as separate packages and follow the protocol; their existence
is informative (charter §3.2 backend-as-sibling-package pattern) and not within the spec
scope.

In-core reference implementations:

- **InMemoryCheckpointer** — keeps records in a Python `dict` (or per-language equivalent).
  Not durable across process crashes. Useful for tests, short-lived runs, and development.
  Accepts any state shape.
- **SQLiteCheckpointer** — persists records to a SQLite database with WAL mode. Durable
  across process crashes within a single host. Accepts any pickleable state shape (Python)
  or any JSON-native shape (cross-language portable mode, configurable). Charter §3.2
  already accepts SQLite as a core dependency for `openarmature-eval`, so adding it for core
  checkpoint is consistent with existing dependency footprint.

Sibling-package adapters (informative, NOT specified by this section):

- `openarmature-temporal` — adapts Temporal's event-journal-and-data-converter to the
  Checkpointer protocol. Multi-day human-in-loop pauses, cross-machine fault tolerance.
- `openarmature-dbos` — adapts DBOS's Postgres-backed step journal. Lighter than Temporal,
  Postgres-native.
- `openarmature-restate` — adapts Restate's RPC-native journal.
- `openarmature-redis-checkpoint` — adapts Redis as a fast networked store; useful for
  multi-worker pipelines on a shared host.

Each adapter package MAY add its own configuration ergonomics on top of the Checkpointer
protocol (e.g., Temporal namespace selection); none change the protocol's behavioral contract.
