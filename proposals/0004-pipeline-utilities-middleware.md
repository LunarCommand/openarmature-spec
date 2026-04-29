# 0004: Pipeline Utilities — Middleware

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-04-28
- **Accepted:**
- **Targets:** spec/pipeline-utilities/spec.md (creates)
- **Related:** 0001, 0003, 0006
- **Supersedes:**

## Summary

Establish the foundational behavioral specification for the OpenArmature pipeline-utilities
capability, beginning with **middleware**: a composable wrapper around node execution that lets
cross-cutting concerns (retry, timing, structured logging, instrumentation) layer on without
modifying node implementations or the engine. The proposal includes a canonical retry middleware as
the first concrete example. Per-node and per-graph registration are both required; middleware does
not cross subgraph boundaries.

## Motivation

Graph-engine §6 (proposal 0003) gave the engine an *observation* primitive — observers see what
happened, but cannot change it. That is insufficient for several common production needs:

- **Retry on transient provider errors.** Local LLM servers (vLLM, LM Studio) and hosted APIs
  (OpenAI, Bifrost) regularly return rate-limit (429) and unavailable (5xx) responses; pipelines
  need to retry without forcing every node author to wrap their own retry loop.
- **Per-node instrumentation.** Timing, request ID propagation, and structured logging are useful
  across many nodes but only worth coding once.
- **Resource lifecycle.** Per-stage GPU model loading and connection-pool checkout are wrap-around
  concerns that don't belong in node bodies.
- **Test seams.** Replacing a node's behavior with a stub or canned response for testing requires a
  short-circuit primitive.

These all share a shape: code that runs around a node call, can read or short-circuit it, and
composes with other code of the same shape. That shape is middleware. The graph-engine spec
(§7 Out of scope) explicitly defers it as a pipeline-utilities concern; this proposal provides it.

The capability is also the prerequisite for two other near-term proposals:

- **Parallel fan-out (proposal 0005, in flight)** uses middleware composition to combine per-fan
  rate limiting with per-node retry.
- **OpenTelemetry span mapping (proposal 0007, in flight)** spans node executions; the span-open
  and span-close points are middleware around node calls (in addition to the §6 observer events,
  which OTel consumes for span attributes).

## Detailed design

The full proposed text of `spec/pipeline-utilities/spec.md` is reproduced below. It is written in
language-agnostic terms — Python and TypeScript map their own idioms (decorators vs. higher-order
functions, async generators vs. callbacks) onto the behavioral contract described here.

The spec version under which this capability lands is determined at acceptance time and recorded in
`CHANGELOG.md`.

---

### 1. Purpose

The pipeline-utilities capability defines a layer of cross-cutting concerns that compose with the
graph-engine without modifying the engine. This first version specifies **middleware** — wrappers
around node execution — and a canonical **retry middleware** as the first concrete instance.

Middleware solves the problem of code that should run around many node invocations without being
duplicated in each node's body. Retry, timing, logging, instrumentation, and resource lifecycle are
all middleware-shaped. Observer hooks (graph-engine §6) cover read-only observation of what
happened; middleware covers control over what happens.

The pipeline-utilities capability composes on top of graph-engine. It does NOT modify graph-engine
behavior — middleware sits between the engine's "node dispatch" step and the user's node function,
and is invisible to nodes that don't opt into middleware.

### 2. Concepts

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
- Short-circuit by NOT calling `next` and returning its own partial update. The wrapped node does
  not execute.
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

### 3. Registration

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

### 4. Subgraph composition

Middleware does NOT cross the subgraph boundary. When a subgraph runs as a node inside a parent:

- The parent's per-graph middleware wraps the subgraph-node dispatch (i.e., the wrapper sees the
  parent's state going in and the projected partial update coming out).
- The parent's per-node middleware on the subgraph-node wraps the same dispatch, inside the
  per-graph middleware.
- The subgraph's own per-graph middleware wraps the subgraph's internal nodes. From the parent's
  perspective these are invisible — they are part of the subgraph's internal execution.
- The subgraph's per-node middleware wraps individual nodes inside the subgraph.

The four sets compose locally to each graph; there is no implicit propagation across the boundary.

This matches the §6 observer hook behavior (graph-engine spec §6, proposal 0003): subgraph-attached
observers fire only for subgraph-internal events, parent-attached observers fire for everything in
the invocation. Middleware follows the same locality principle.

### 5. Error semantics

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

**The §6 observer event** for a node execution is dispatched once per node *after the entire
middleware chain completes* (success or failure). The event carries the *final* partial update (or
the *final* error) seen by the engine, not intermediate values that middleware may have produced
internally. Middleware-internal retries are invisible to observers — what observers see is the
single attempt that succeeded or the single failure that propagated. (Implementations MAY expose
middleware-internal observation through a separate mechanism; that is out of scope here.)

**Recoverable state semantics** (graph-engine §4) are unchanged. If a middleware exception
ultimately propagates, the engine's `node_exception` carries the pre-merge state, identical to the
case where the node itself raised.

### 6. Retry middleware (canonical)

Implementations MUST provide a retry middleware as part of the pipeline-utilities surface. The
configuration record:

| Field | Description |
|---|---|
| `max_attempts` | Int, default `3`. Total attempts including the first call. `1` disables retry. |
| `classifier` | Predicate `(exception) -> bool`. Returns `true` if the exception is retryable. Default: matches the well-known transient categories (see below). |
| `backoff` | Callable `(attempt_index) -> seconds`. `attempt_index` is 0-based. Default: exponential with full jitter, base 1s, cap 30s. |
| `on_retry` | Optional async callback `(exception, attempt_index) -> None`. Fires before each sleep. Implementations MAY use this for logging hooks. |

Behavior:

```
attempt = 0
while True:
    try:
        return await next(state)
    except Exception as exc:
        if not classifier(exc) or attempt + 1 >= max_attempts:
            raise
        if on_retry is not None:
            await on_retry(exc, attempt)
        await sleep(backoff(attempt))
        attempt += 1
```

**Default transient classifier.** The default classifier MUST return `true` for exceptions whose
error category (per the carrying spec) is one of:

- `provider_unavailable` (llm-provider §7)
- `provider_rate_limit` (llm-provider §7)
- Any exception whose carrying spec marks it transient

It MUST return `false` for:

- `provider_authentication`, `provider_invalid_model`, `provider_invalid_request`,
  `provider_invalid_response` (llm-provider §7)
- All graph-engine §2 compile errors (these will not arise at runtime, but listed for completeness)
- All graph-engine §4 errors except as carrier wrappers (a `node_exception` whose `__cause__` is a
  transient category MUST be classified as transient).

Forward dependency: the categories above are normative as of llm-provider §7. If a §7 category is
added, removed, or reclassified by a later proposal, the default classifier MUST be updated in lock-
step (a clarification PATCH).

**Backoff with full jitter.** The default backoff is `random.uniform(0, min(cap, base * 2^attempt))`
where `base = 1.0` and `cap = 30.0`. The jitter is mandatory — fixed exponential backoff causes
synchronized retries from many concurrent callers, amplifying the rate-limit storm. Implementations
MAY provide additional named backoff strategies (constant, linear, exponential without jitter) but
MUST default to exponential-with-full-jitter.

**Partial-update inspection.** A retry middleware MUST NOT retry on a successful `next(state)` call
that returns an "error-shaped" partial update — partial updates are not exceptions, and the engine's
contract is that nodes signal failure by raising. If a node returns `{"error": "..."}` as data, that
is application data, not a retry trigger.

### 7. Determinism

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

### 8. Out of scope

Not covered by this specification; deferred to follow-on proposals or capabilities:

- **Parallel fan-out / fan-in** — proposal 0005.
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

## Conformance test impact

Add a new conformance directory `spec/pipeline-utilities/conformance/` with the following fixtures.
Each is a YAML pair (input + expected) plus a markdown description.

1. **`001-middleware-basic-firing`** — single node with one per-node middleware that records the
   pre/post state. Verifies the middleware sees the input state and the partial update returned by
   the node, and the engine merges normally.

2. **`002-middleware-composition-ordering`** — single node with three middleware [m1, m2, m3].
   Each middleware appends to a list-typed `trace` field. Verifies execution order is m1→m2→m3→node
   on the way in and node→m3→m2→m1 on the way out.

3. **`003-middleware-per-graph-vs-per-node-composition`** — graph with two per-graph middleware and
   a node with two per-node middleware. Verifies the composition order: per-graph[0] → per-graph[1]
   → per-node[0] → per-node[1] → node.

4. **`004-middleware-short-circuit`** — middleware returns a partial update without calling `next`.
   Verifies the wrapped node does not execute (its trace marker does not appear) and the partial
   update from the middleware is what the engine merges.

5. **`005-middleware-error-propagation`** — node raises; middleware does not catch. Verifies the
   error propagates as `node_exception` per graph-engine §4, with recoverable state and `__cause__`
   preserved.

6. **`006-middleware-error-recovery`** — node raises; middleware catches and returns a partial
   update. Verifies execution continues normally; observer event has `post_state` populated (no
   `error`); final state reflects the recovery partial update.

7. **`007-retry-middleware-success-on-second-attempt`** — node fails on first call (mocked
   transient exception), succeeds on second. Verifies retry middleware retries, the second call
   succeeds, and the engine sees one combined success.

8. **`008-retry-middleware-exhausted`** — node fails repeatedly with a transient exception;
   `max_attempts=3`. Verifies the engine eventually receives the exception (categorized as
   `node_exception`); recoverable state is correct.

9. **`009-retry-middleware-non-retryable-passthrough`** — node fails with a non-transient exception;
   classifier returns false. Verifies the middleware does NOT retry; the exception propagates
   immediately.

10. **`010-middleware-subgraph-isolation`** — outer graph with per-graph middleware; inner subgraph
    with its own per-graph middleware. Verifies the outer's middleware fires for the subgraph
    dispatch but NOT for the subgraph's internal nodes; the subgraph's middleware fires for its
    internal nodes only.

11. **`011-middleware-determinism`** — graph with a deterministic retry middleware (jitter swapped
    for a fixed backoff), two runs against an identical mocked-failure-then-success scenario.
    Verifies final state and observer event sequence are identical across runs.

The conformance harness in each implementation supplies a mock-transient-exception adapter for the
retry fixtures; live LLM provider calls are out of scope for this suite.

## Alternatives considered

**Do nothing — let users wrap their own.** Already what every prototype does, and the friction is
real: each node author writes the same retry-loop boilerplate, and instrumentation gets bolted on
inconsistently. Rejected for the same reason graph-engine itself exists: shared infrastructure
beats duplicated infrastructure.

**Use observer hooks (graph-engine §6) for everything.** Observer hooks are *read-only*. They cannot
retry, cannot short-circuit, cannot modify the partial update. They are excellent for monitoring and
logging but cannot satisfy the retry requirement. The two layers are complementary: observers tell
you what happened; middleware decides what happens.

**A `before` and `after` hook pair instead of single-callable middleware.** Two separate callbacks
(`before(state) -> state` and `after(state, partial_update) -> partial_update`) would simplify the
common case (instrumentation, logging) but make retry awkward (no natural seam to loop). The single-
callable shape with `next` is the standard middleware pattern (Express.js, Connect, Tower, ASGI, Koa,
Express, Django middleware, etc.) and handles both linear and looping uses cleanly.

**Stack-based middleware (engine pushes/pops a context).** Common in Rails / Sinatra. Rejected
because it requires the engine to manage a per-call stack, which makes async composition (especially
across subgraph boundaries) more complex. The functional `next`-passing shape is naturally async-
correct and trivially composable.

**Allow middleware on conditional edges.** Wrapping edges is occasionally useful (logging routing
decisions, retrying flaky edge functions). Deferred to a follow-on proposal because (a) edge
functions are simpler than nodes (no merge step, no partial update) so the middleware shape would
differ slightly, (b) conditional edge errors are already covered by graph-engine §4
`edge_exception`, and (c) the immediate need is around node calls.

**Middleware can modify the input state's identity (replace the state passed to `next`).** Currently
spec'd: yes, middleware MAY pass a transformed state to `next`. An alternative would be: state is
read-only at this seam, only the partial update can be modified. Rejected because retry middleware
sometimes needs to pass a modified state on subsequent attempts (e.g., add a retry-attempt counter
to the state for the node to observe). The transformation only affects what the wrapped node sees,
not what the engine merges (the engine already has the pre-state from before any middleware ran).

**Cross-subgraph propagation of middleware.** A single middleware registered on the parent could
automatically apply to every node anywhere in the call tree (parent + nested subgraphs). Rejected
for symmetry with graph-engine §6 observer hooks, which already chose locality. Cross-subgraph
propagation is sometimes useful (uniform logging across all nodes anywhere) but breaks composition
(a subgraph compiled for use in many parents would behave differently in each, depending on the
parent's middleware set). Locality is more predictable.

**Bake the default classifier into a fixed list of strings.** Currently the spec says the default
classifier matches well-known transient categories and forward-references llm-provider §7. The
alternative — no defaults, every user supplies a classifier — was considered. Rejected because the
common case (retry on rate limits and 5xx) needs to work out of the box; making every user
re-derive the classifier from scratch is the same kind of friction the framework exists to remove.

**Middleware can register more middleware dynamically during a run.** Rejected. Same rationale as
graph-engine §6 observer hooks: the set of middleware is fixed for an invocation. Dynamic
registration would make composition order ambiguous and complicate determinism.

## Open questions

1. **Should middleware see the §6 observer event before it dispatches?** Currently the spec says
   observers see the *final* partial update (or final error) after all middleware. This is the
   simple thing. An alternative: observers see one event per "attempt" (so retries are visible in
   the observer stream). The simple thing is shipped; revisit if production users want
   per-attempt visibility and can't get it through middleware-internal logging.

2. **Per-conditional-branch middleware?** A middleware that applies only to nodes routed-to from
   a specific conditional edge. Probably not worth a registration mode of its own — users can put
   the middleware on the target node directly. Defer.

3. **Should `RetryMiddleware.classifier` see the post-merge state in addition to the exception?**
   The current shape is `classifier(exception) -> bool`. Adding `state` would let
   "retry only if some field is X" classifiers work, but makes the contract more complex. Defer
   until a real use case surfaces.

4. **Should the retry middleware emit observer events on retries?** Currently retries are invisible
   to observers (only the final attempt's event fires). Emitting per-attempt events would help
   debugging but couples retry middleware to graph-engine §6 details. Could be added as an
   `on_retry` instrumentation callback (already in the config record) without expanding the
   observer event surface.
