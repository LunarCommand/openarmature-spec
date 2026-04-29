# Pipeline Utilities

Canonical behavioral specification for the OpenArmature pipeline-utilities capability.

- **Capability:** pipeline-utilities
- **Introduced:** spec version 0.5.0
- **History:**
  - created by [proposal 0004](../../proposals/0004-pipeline-utilities-middleware.md)

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

**The §6 observer event** for a node execution is dispatched once per *attempt* (per the §6
"Middleware-dispatched events" subsection). For nodes wrapped by middleware that re-attempts (such
as retry), each attempt produces its own event with `attempt_index` set; the final attempt's event
is dispatched by the engine, while non-final attempts' events are dispatched by the middleware.
For nodes not wrapped by re-attempting middleware, the §6 contract behaves exactly as before:
exactly one event per node execution, with `attempt_index == 0`.

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
        return await next(state)         # final attempt's event is dispatched by the engine
    except Exception as exc:
        if not classifier(exc, state) or attempt + 1 >= max_attempts:
            raise                        # terminal — the engine dispatches the event with `error`
        dispatch_failed_attempt_event(   # see "Per-attempt observer events" below
            attempt_index=attempt,
            exception=exc,
        )
        if on_retry is not None:
            await on_retry(exc, attempt)
        await sleep(backoff(attempt))
        attempt += 1
```

**Per-attempt observer events.** Each non-final retry attempt MUST dispatch a node event onto
the §6 observer delivery queue (per graph-engine §6's "Middleware-dispatched events" subsection).
The dispatched event has `attempt_index` set to the attempt's 0-based index, `error` populated
with the §4 category and the raised exception, and the same `node_name` / `namespace` / `step` /
`pre_state` / `parent_states` the engine-dispatched event for that attempt would have carried.
The final attempt's event is dispatched by the engine on the normal §6 dispatch step (with
`attempt_index` set to the final attempt's index and either `post_state` populated on success
or `error` populated on terminal failure). Net result: N events for an N-attempt retry —
N-1 from the middleware, 1 from the engine — with `attempt_index` values `0..N-1` in order.

The dispatch mechanism is implementation-defined per graph-engine §6's "Middleware-dispatched
events" subsection. Implementations MUST surface a per-language API on the middleware execution
context so retry can call it without inspecting engine internals.

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

- **Parallel fan-out / fan-in** — proposal 0005 (in flight).
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
