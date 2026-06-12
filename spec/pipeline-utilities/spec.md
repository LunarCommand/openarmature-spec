# Pipeline Utilities

Canonical behavioral specification for the OpenArmature pipeline-utilities capability.

- **Capability:** pipeline-utilities
- **Introduced:** spec version 0.5.0
- **History:**
  - created by [proposal 0004](../../proposals/0004-pipeline-utilities-middleware.md)
  - §9 Parallel fan-out added; §6.1 Retry middleware simplified (manual event dispatch removed in coordination with graph-engine §6's pair model) by [proposal 0005](../../proposals/0005-pipeline-utilities-parallel-fan-out.md)
  - §10 Checkpointing added by [proposal 0008](../../proposals/0008-pipeline-utilities-checkpointing.md)
  - §11 Parallel branches added by [proposal 0011](../../proposals/0011-pipeline-utilities-parallel-branches.md)
  - §10.2 `schema_version` reframed as user-facing; §10.10 `checkpoint_record_invalid` description amended and two new error categories (`checkpoint_state_migration_missing`, `checkpoint_state_migration_failed`) added; §10.12 State migrations added by [proposal 0014](../../proposals/0014-pipeline-utilities-state-migration.md)
  - §10.10 gained canonical configuration-time category `checkpoint_state_migration_chain_ambiguous`; §10.12.1 and §10.12.2 updated to reference the category by name; mutual-exclusion paragraph rewritten for four migration-related categories by [proposal 0018](../../proposals/0018-state-migration-chain-ambiguity.md)
  - §10.2 `fan_out_progress` field promoted from reserved to populated; §10.3 save-granularity rule extended to fan-out instance internal nodes (the "engine does NOT save during fan-out instance execution" rule is removed); §10.7 atomic-restart fan-out resume replaced with per-instance resume; §10.11 added (per-instance fan-out resume contract — accumulator semantics, reducer interaction, error_policy / instance_middleware composition, configurable Checkpointer-level batching for fan-out internal saves); existing §10.11 (Reference implementations and backend layering) renumbered to §10.13 by [proposal 0009](../../proposals/0009-pipeline-utilities-per-instance-fan-out-resume.md)
  - §10.11 per-instance entry shape gained `result_is_error: bool` field (success vs `collect`-mode-error discriminator for resume routing); §10.11.2 `collect` bullet amended to name the field as the discrimination mechanism and forbid heuristic inspection of `result` shape by [proposal 0027](../../proposals/0027-fan-out-instance-progress-result-is-error.md)
  - §10.2 `schema_version` paragraph clarified: the outermost declared graph state class is the canonical source for the value written onto saved records; implementations MUST NOT source `schema_version` from the runtime instance's class when a State subclass shadows the declared value by [proposal 0028](../../proposals/0028-schema-version-canonical-source.md)
  - §10.11 gained a "Count drift on resume" rule: when a saved `fan_out_progress` entry's `instance_count` differs from the resumed run's resolved count, the engine MUST raise `checkpoint_record_invalid` (per §10.10); silent pad/truncate of the saved `instances` list is not permitted. §10.10 `checkpoint_record_invalid` description extended to enumerate count drift as a failure mode by [proposal 0029](../../proposals/0029-count-drift-strict.md)
  - §10.14 *Composition with sessions* added — notes that the new sessions capability is an orthogonal cross-invoke persistence layer; checkpointing and sessions register independently, MAY share a backend, but resume / session-load and the respective error categories surface independently by [proposal 0020](../../proposals/0020-sessions-capability.md)
  - §6.3 *Failure isolation* middleware added as the third canonical primitive in the §6 bundled set (alongside §6.1 Retry and §6.2 Timing) — packages the §2 third-MAY-bullet catch-and-recover pattern with a four-field configuration record (`degraded_update` [static or callable], `event_name` [required, no default — naming decision at construction site], `predicate` [single-arg `(exception) -> bool`, defaults to always-true], `on_caught` [optional async callback]); catches `Exception` (not `BaseException`); on catch dispatches a framework-emitted failure-isolation event onto the observer delivery queue (parallels proposal 0040's metadata-augmentation event mechanism — distinct from `NodeEvent`, carries `event_name` + wrapped-node lineage tuple + `pre_state` / `post_state` + `caught_exception` record; not promoted to a typed variant on the observer event union for v1) and returns the configured degraded update so the engine continues edge resolution normally; documents the three-piece composition pattern with §6.1 retry (outer-to-inner: transient-aware node body + inner Retry + outer FailureIsolation) with outer-to-inner ordering load-bearing by [proposal 0050](../../proposals/0050-retry-and-degradation-primitives.md)
  - §10.15 *Composition with suspension* added — notes that the new suspension capability uses the same persistence mechanism as checkpointing for paused-invocation records (single store with discriminator OR separate stores; implementation choice); paused-invocation records and checkpoint records are distinct shapes; resume operations load the correct record type per the resume API in use (`invoke(resume_invocation=...)` per §10.4 → checkpoint record; `invoke(resume_invocation=..., signal_payload=...)` per suspension §7 → paused-invocation record); paused-record lifetime is NOT bound to invocation completion (unlike checkpoint records, persists until resume completes / cancellation / backend retention); error categories are distinct (`suspension_persistence_failed` per suspension §9 does not signal checkpoint failure and vice versa). Refer to the suspension capability spec for the full primitive contract by [proposal 0021](../../proposals/0021-graph-suspension.md)

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
pair model). For nodes whose execution is wrapped by middleware that re-attempts (such as retry)
— including both **direct** wrapping (the node's per-node middleware chain) and **transitive**
wrapping (middleware on a containing subgraph: §9.7 instance middleware, §11.7 branch middleware)
— each attempt produces its own started/completed pair with `attempt_index` set per graph-engine
§6. The engine dispatches all events — middleware does not dispatch directly. The mechanism by
which a wrapping retry's attempt counter propagates to inner-node event emissions is implementation-
defined (Python: a `contextvars.ContextVar` set by the retry middleware before each `next` call;
TypeScript: `AsyncLocalStorage` or equivalent). When multiple retry middlewares wrap the same
execution (e.g., a per-node retry directly on the node combined with a branch-level retry on a
containing subgraph), the innermost retry's counter wins per graph-engine §6's precedence rule.
For nodes with no re-attempting middleware anywhere in the wrapping chain, every attempt is a
single execution that still produces a started/completed pair, with `attempt_index == 0`.

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

### 6.3 Failure isolation

The failure-isolation middleware catches exceptions escaping the inner chain and returns a
configured degraded partial update. The named primitive packages the §2 third-MAY-bullet pattern
("middleware MAY catch ... and either re-raise, transform, or recover") with a stable contract
and observer-event surface, avoiding per-downstream re-derivation of the catch-and-recover
shape.

The failure-isolation middleware configuration record:

| Field | Description |
|---|---|
| `degraded_update` | Required. The partial state update returned on caught exceptions. MAY be a static mapping OR a callable `(state) -> partial_update` for cases where the degraded shape depends on input state. Resolved at catch time; the callable form receives the same `state` argument the middleware received (pre-merge state on the failed inner chain). |
| `event_name` | Required, no default. A stable identifier for this catch site. Surfaces on the framework-emitted failure-isolation event (see below). Required with no default because useful values are node-specific (e.g., `"segment_extraction_failure_isolated"`) — a generic `"failure_isolated"` default would make downstream telemetry strictly worse by hiding which specific path degraded. Forcing the name at the construction site puts the decision where the right context is available. |
| `predicate` | Optional. A callable `(exception) -> bool`. When supplied, only exceptions where `predicate(exc) is True` are caught; others propagate. Defaults to "always True" (catch all `Exception`). Single-argument signature (compare §6.1's two-argument retry classifier) — state-dependent failure-isolation predicates are not a documented use case; the simpler signature is sufficient for v1. |
| `on_caught` | Optional. An async callable `(exception) -> Awaitable[None]`. Fires when the middleware catches an exception. Lets consumers pump caught exceptions to caller-specific telemetry (custom logger, metric counter, etc.) beyond the default observer event. |

Behavior:

```
try:
    return await next(state)
except Exception as exc:
    if not predicate(exc):
        raise
    resolved_update = degraded_update(state) if callable(degraded_update) else degraded_update
    await emit_failure_isolation_event(           # see *Observability* below
        event_name=event_name,
        wrapped_node_lineage=<from graph-engine §6 event-source identity tuple>,
        pre_state=state,
        post_state=resolved_update,
        caught_exception=<category + message>,
    )
    if on_caught is not None:
        await on_caught(exc)
    return resolved_update
```

The resolution of `resolved_update` happens BEFORE event emission so the event's `post_state`
field carries the resolved degraded payload (observers correlate the wrapped node's input state
on `pre_state` with the actual partial update the engine will merge on `post_state`).
`emit_failure_isolation_event` is the framework's observer-queue dispatch path described below.

**Catch semantics.** Catches `Exception` by default; `BaseException` (cancellation,
`KeyboardInterrupt`, equivalents) propagates uncaught — the same rule §6.1 retry middleware
applies. Cancellation signals MUST propagate per the §6.1 cancellation-propagation paragraph.

**Engine continuation.** On a caught exception, the graph engine continues edge resolution from
the `FailureIsolationMiddleware`-wrapped node's degraded return per the normal §3 / §4 contract.
The engine does NOT see the exception; from its perspective, the node returned normally.

**Observability.** When the middleware catches an exception, it dispatches a **framework-emitted
failure-isolation event** onto the same observer delivery queue as `NodeEvent` per graph-engine
§6. The event is a distinct kind from `NodeEvent` — it does NOT reuse `NodeEvent.node_name` /
`namespace` (which graph-engine §6 reserves for registered-node identity) and does NOT reuse
`NodeEvent.error` (a graph-engine §4 category). It is a separate framework-emitted observer
event variant carrying its own field set:

- `event_name` — the caller-supplied event name from the middleware's configuration.
- The wrapped node's lineage identity per graph-engine §6: `namespace`, `attempt_index`,
  `fan_out_index`, `branch_name` — the same lineage tuple `NodeEvent` carries, surfaced here for
  correlation with the wrapped node's other events.
- `pre_state` — the state the wrapped node's inner chain received (the middleware's `state`
  argument).
- `post_state` — the resolved degraded partial update being returned to the engine.
- `caught_exception` — a structured record carrying the caught exception's category (per its
  carrying spec, e.g., llm-provider §7 / graph-engine §4) and the exception message. When the
  caught exception does not carry a category (e.g., a bare `ValueError`), the category field is
  `null` and the message captures the exception's `str(exc)` form.

**Cause fidelity at carrier-wrapper sites.** `caught_exception.category` MUST reflect the
**originating** failure. When the caught exception is a graph-engine §4 `node_exception` carrier
wrapper — which it is at any non-node placement where the engine has wrapped the originating error
before the isolation middleware catches it (§9.7 instance middleware, §11.7 branch middleware, or
parent-node middleware on a fan-out / parallel-branches node per §9.6 / §11.6) — the middleware
MUST resolve through the carrier wrapper to the originating cause (`__cause__`) and report that
category. This is the same carrier-wrapper resolution §6.1's default classifier mandates (a
`node_exception` whose `__cause__` is a transient category MUST be classified as transient).
Resolution walks nested carrier wrappers to the originating cause. When the originating cause
carries no category (e.g., a bare `ValueError`), the category is `null` per the rule above. At
node-level placement no carrier wrapper is present — the middleware catches the raw error — so no
resolution applies and the category is the raw error's. `caught_exception.message` SHOULD describe
the same originating cause the category resolves from, so the event's `category` and `message`
refer to one exception rather than pairing a resolved category with the wrapper's message.

**Wrapped-instance / branch lineage.** At the non-node wrapping sites above, the isolation
middleware runs outside the engine's per-instance / per-branch scope, so the lineage tuple can
resolve to the wrapping node's identity rather than the isolated instance's / branch's. Where the
per-instance / per-branch identity is recoverable, the event's lineage (`namespace`,
`fan_out_index`, `branch_name`) SHOULD resolve to the wrapped instance / branch. This is a SHOULD,
not a MUST: recovering the identity may require the engine to surface it to the wrapping-site
middleware, whereas the category fidelity above needs only inspection of the already-caught
exception.

This pattern parallels graph-engine §6's RECOMMENDED metadata-augmentation event mechanism (from
proposal 0040) — a distinct framework-emitted event kind on the observer delivery queue, with
the typed shape per-language idiom. The spec mandates the event mechanism + field set;
per-language implementations choose the concrete typed shape (e.g., a Python dataclass, a
TypeScript interface) following the language's naming idioms. A future proposal MAY promote the
failure-isolation event to a spec-mandated typed variant on the observer event union
(paralleling proposal 0049's `LlmCompletionEvent` carve-out) if the middleware-event pattern
accumulates across multiple primitives; for v1, the event-mechanism framing is sufficient.

**Default emission is observer-event-only.** The middleware MUST NOT pin a logging library
(stdlib `logging`, structlog, etc.) — the default emission path is the observer event.
Consumers wanting additional logging attach their own observer or use `on_caught`.

**Composition with §6.1 — the three-piece pattern.** Pipelines that want "retry transients,
give up gracefully on exhaustion or non-transient errors" compose three pieces:

1. **Node body** keeps a transient-aware `except` block — re-raise on exceptions whose
   category §6.1's default classifier treats as transient (`provider_unavailable`,
   `provider_rate_limit`, etc.), degrade in-place on non-transient categories the application
   already knows how to recover from.
2. **Inner middleware**: `RetryMiddleware` (§6.1) — sees raw transients and retries them per
   its policy; on exhaustion, propagates the exception.
3. **Outer middleware**: `FailureIsolationMiddleware` (this section) — catches the
   exhaustion-propagated exception (or any non-transient that re-raised through the node
   body's `except`) and returns the configured degraded update.

Outer-to-inner ordering is load-bearing: retry MUST be inner (it sees raw transients first);
failure isolation MUST be outer (it only sees what escapes retry). Reversing the order would let
the inner isolation catch transients before retry sees them, defeating retry's purpose entirely.
Implementations SHOULD document this composition explicitly in the middleware API documentation.

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
order via the parent's reducer for the named field. The reducer for `target_field` MUST accept
the engine-produced list of per-instance values (`[s[collect_field] for s in successes]`) as
its `update` argument. Permitted graph-engine §2 built-ins: `append` (list-of-X → list-of-X),
`concat_flatten` (list-of-list-of-X → list-of-X; for cases where per-instance values are
themselves list-shaped), and `merge_all` (list-of-mapping → mapping; for cases where
per-instance values are dict-shaped and the parent wants a single merged dict). User-defined
reducers MAY also be used, provided their `update` argument accepts the engine-produced list.
The reducer for any field named in `extra_outputs` MUST accept the value type the subgraph
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

- `invocation_id` — string. Per observability §5.1; caller-supplied or framework-generated
  (used verbatim when the caller supplies one at invoke time; otherwise a framework-minted
  UUIDv4). A resume mints a FRESH `invocation_id` — each attempt is its own invocation (§5.1),
  so a resumed record's `invocation_id` differs from the original's and any caller-supplied
  `invocation_id` is ignored on the resume path. Correlate attempts via `correlation_id`
  (below), which is invocation-scoped and stable across resume.
- `correlation_id` — string. Per observability §3; caller-supplied or framework-generated;
  flows unchanged across resume (a resumed invocation keeps the original `correlation_id`,
  which is invocation-scoped).
- `state` — the post-merge outermost state at the latest save point. Type is the user's
  declared outermost state schema (graph-engine §1).
- `completed_positions` — ordered sequence of `NodePosition` records, one per completed node
  attempt that has been merged. Each position carries `namespace` (per graph-engine §6),
  `node_name`, `step` (monotonic across the invocation, including subgraph-internal nodes),
  `attempt_index`, and `fan_out_index` (when present).
- `fan_out_progress` — per-fan-out-node mapping populated when one or more fan-outs are in
  flight at save time. Drives per-instance fan-out resume (per §10.7 and §10.11): on resume,
  the engine consults this field to skip already-completed instances and re-run only those
  that did not complete-and-record before the crash. Field shape (per-fan-out entry,
  per-instance status with accumulator `result`, in-flight `completed_inner_positions`) is
  specified in §10.11. Absent when no fan-out is in flight at the save point.
- `parent_states` — when the latest save point is inside a subgraph or fan-out instance, the
  ordered sequence of containing-graph states (outermost first). Per graph-engine §6
  semantics; preserved across resume so the engine can re-enter the subgraph correctly.
- `last_saved_at` — timestamp. Implementation-defined precision; SHOULD be monotonic per
  invocation (later saves have later timestamps).
- `schema_version` — string. Carries the version identifier of the user's state schema at the
  time the record was saved. The state definition MAY expose a stable, user-controlled
  `schema_version` identifier (the surface for declaring it is per-language ergonomic — e.g.,
  a class attribute in Python, a constant in TypeScript). State classes that do not declare a
  `schema_version` are treated as carrying an implementation-defined sentinel value (typically
  the empty string), and are not migration-eligible until they declare one. Users intending to
  evolve their schema across deploys MUST declare an explicit `schema_version` so that
  migrations (per §10.12) can be registered against it. **The framework reads `schema_version`
  from the outermost declared graph state class** (the state class passed to the graph
  constructor — e.g.,
  `GraphBuilder(MyState)` in Python or the equivalent in another language idiom) at save
  time and writes that value onto the record. Implementations MUST NOT source
  `schema_version` from the runtime instance's class (e.g., `type(state).schema_version` in
  Python) when the user passes a State subclass instance whose `schema_version` shadows the
  declared class's value — the declared class is the canonical source for all save sites in
  the engine (outermost-graph saves, subgraph-internal saves, fan-out instance internal
  saves, fan-out node completion saves), so resume sees a single consistent `schema_version`
  and the §10.12 migration registry's `from_version`/`to_version` lookups resolve
  unambiguously. The framework does not constrain the version identifier's syntax;
  users MAY use semver, integer counters, date stamps, or content hashes — whatever makes
  sense for their evolution discipline. Two distinct identifiers are treated as distinct
  versions; identical identifiers are treated as the same version.

### 10.3 Save granularity — every `completed` event

The engine fires a save at every graph-engine §6 `completed` event from the following sources:

- **Outermost-graph nodes.** One save per node attempt that finishes (successful merge or
  failure captured).
- **Subgraph-internal nodes.** One save per inner-node completion, with `parent_states`
  populated per §10.2. Resume can re-enter the subgraph at any boundary; long-running
  subgraphs benefit directly from per-inner-node save granularity.
- **Fan-out instance internal nodes.** One save per inner-node completion within an
  instance. `parent_states` is populated per §10.2 (the fan-out instance's outer state is
  the parent); `fan_out_progress` is populated per §10.11 to disambiguate which
  `fan_out_index` slot the event belongs to. This save granularity is what enables the
  per-instance resume contract of §10.7. For high-instance-count or high-inner-node-count
  fan-outs whose internal save volume is a concern, Checkpointer backends MAY support
  configurable batching scoped to fan-out internal saves per §10.11.4.
- **Fan-out node itself** (the parent dispatch node, per pipeline-utilities §9). One save when
  the fan-out as a whole has finished and its results have merged back into outer state.
  This save also finalizes `fan_out_progress` to mark all instances complete.

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

### 10.7 Fan-out resume — per-instance

When a fan-out is in flight at crash time (some instances completed and recorded their
contribution into the fan-out accumulator; some in-flight; some not yet started), resume
re-runs **only the instances that did not complete-and-record**. Instances whose
contributions are already in the accumulator are skipped; their accumulator entries roll
forward to the fan-out's fan-in step (per §9.3) at fan-out completion.

Per-instance results are recorded into a **fan-out-local accumulator** (the per-instance
`result` entries in `fan_out_progress`, defined in §10.11) as instances complete. Parent
state is NOT mutated per-instance — the existing §9.3 contract (parent state mutations
happen at the fan-in step after ALL instances complete) is preserved unchanged. The
accumulator is durable across crashes via the `fan_out_progress` field on
`CheckpointRecord`; it rolls forward on resume so that already-completed instances'
contributions are not lost.

On resume into a fan-out that was in flight at crash time, the engine consults the saved
record's `fan_out_progress` field and treats each instance as one of three states:

- **Completed.** The instance ran to completion in the prior execution and recorded its
  durable contribution into the fan-out accumulator (the entry's `result` field per
  §10.11). The contribution is path-agnostic: a success result for the `target_field`
  bucket, or in `collect` error_policy mode (per §9.5), a recorded error for the
  `errors_field` bucket. On resume, the engine MUST NOT re-run the instance and MUST NOT
  record a second accumulator entry. The instance is skipped; its accumulator entry rolls
  forward to the fan-out's fan-in step (per §9.3) at fan-out completion.
- **In-flight at save time.** The instance had begun execution (its first inner node fired
  `started`) at the moment of save AND no `completed` event for its terminal inner node
  had fired yet, so no accumulator entry was recorded. On resume, the engine re-runs the
  instance from its entry point with the same projected per-instance state as the original
  run. The re-run instance's terminal inner node `completed` event records the
  contribution into the accumulator for the first time (the original attempt contributed
  nothing because it never reached the completed-and-recorded step). `in_flight` is
  observable in the saved record only when a sibling instance's `completed` event triggers
  a save during this instance's execution — that save snapshots all concurrent instances'
  states, capturing the still-running ones with their accumulated
  `completed_inner_positions`. If no sibling completes before the crash, the saved record
  either does not exist (no save fired yet) or reflects the pre-fan-out save (all
  instances `not_started`), and resume re-dispatches each instance normally; re-dispatch
  is correctness-preserving because no accumulator entry was persisted.
- **Not yet started.** The instance had not been dispatched at save time. On resume, the
  engine dispatches the instance normally.

Per-instance resume composes with the fan-out reducer (§10.11.1), `error_policy`
(§10.11.2), and `instance_middleware` (§10.11.3); details are in §10.11. Backends MAY
opt into configurable batching for fan-out internal saves to bound the write volume of
high-instance-count fan-outs, with the explicit cost trade-off documented in §10.11.4.

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

Canonical runtime category: `checkpoint_record_invalid` — raised when
`Checkpointer.load(X)` returns a record whose schema is incompatible with the current graph
(state shape mismatch, missing required fields, a post-migration state that fails to
deserialize against the current state class per §10.12.4, OR a version mismatch on a
Checkpointer backend that cannot support state migration per §10.12.1). The category also
covers `fan_out_progress[*].instance_count` drift between save and resume per §10.11 — a
saved per-instance accumulator shape that is structurally incompatible with the resumed
run's resolved count. Non-transient. (Prior to proposal 0014, "incompatible
`schema_version`" appeared in this list as a generic reason; raw `schema_version`
mismatches now route through `checkpoint_state_migration_missing` or
`checkpoint_state_migration_failed` per §10.12 on migration-capable backends, and only
fall back to `checkpoint_record_invalid` when the backend itself cannot expose the
class-independent intermediate the migration system requires.)

New canonical runtime category: `checkpoint_state_migration_missing` — raised on
`invoke(resume_invocation=X)` when the loaded record's `schema_version` does not match the
current state schema's `schema_version` AND no chain of registered migrations connects the
two. Non-transient. The error MUST carry at least the record's `schema_version`, the
current schema's `schema_version`, and a description of the registered migration set (in a
form appropriate to the host language) so the user can see what migrations would need to be
added.

New canonical runtime category: `checkpoint_state_migration_failed` — raised when a
user-supplied migration function raises during chain application (per §10.12.2).
Non-transient (a buggy migration is deterministic; retrying without changing the migration
code will not succeed). The error MUST carry the failing migration's `from_version` and
`to_version`, and the underlying exception as cause (per the language's idiom).

New canonical configuration-time category: `checkpoint_state_migration_chain_ambiguous` —
raised when the registered migration set contains an ambiguity that prevents the engine
from picking a unique chain. Two cases trigger this category:

- **At registration (per §10.12.1).** Two migrations registered with the same
  `from_version` AND the same `to_version`. The engine MUST raise this category at
  registration time (or at compile time when migrations are bound to the compiled graph,
  per the host language's binding semantics) so the configuration error surfaces before
  any resume attempt.
- **At chain resolution (per §10.12.2).** A request to resolve a chain from
  `from_version` A to `to_version` B finds two or more distinct shortest paths (same
  edge count, different edge sequences). Implementations SHOULD detect this at compile
  time when feasible by scanning the registered migration graph; load-time detection
  is acceptable when compile-time analysis is not.

Non-transient. The error MUST identify the offending `(from_version, to_version)` pair
(for the registration case) or the source / target version pair and a description of the
conflicting paths (for the resolution case), in a form appropriate to the host language.

The four migration-related categories — `checkpoint_record_invalid`,
`checkpoint_state_migration_missing`, `checkpoint_state_migration_failed`, and
`checkpoint_state_migration_chain_ambiguous` — are mutually exclusive on any given resume:
the engine evaluates registry well-formedness first (routing through
`checkpoint_state_migration_chain_ambiguous` if a duplicate-pair or multi-shortest-path
ambiguity is detected at build or load time), then version compatibility (routing
through `checkpoint_state_migration_missing` if no chain exists), then applies the chain
(routing through `checkpoint_state_migration_failed` if a migration raises), then
attempts deserialization (routing through `checkpoint_record_invalid` if the
post-migration state cannot deserialize).

Version mismatches on Checkpointer backends that cannot support state migration (per
§10.12.1) bypass the migration system entirely and route directly to
`checkpoint_record_invalid` — the migration_missing/migration_failed branch is reachable
only on backends that can expose the required class-independent intermediate form.

### 10.11 Per-instance fan-out resume

The `CheckpointRecord.fan_out_progress` field is a per-fan-out-node mapping (when one or more
fan-outs are in flight at save time). Each entry carries:

- `fan_out_node_name` — the name of the fan-out node in the parent graph.
- `namespace` — the §6 namespace identifying the fan-out node uniquely (handles nested
  subgraphs that contain fan-outs).
- `instance_count` — the resolved instance count for this fan-out (per §9 `count` or
  `items_field` mode).
- `instances` — a sequence of per-instance status entries indexed by `fan_out_index` (`0` to
  `instance_count - 1`). Each entry carries:
  - `state` — one of `completed`, `in_flight`, `not_started`.
  - `result` — for `completed` entries, the instance's durable contribution to the fan-out
    accumulator. For success (any error_policy), the value contributed to the `target_field`
    bucket; for `collect`-mode failures, the error entry contributed to the `errors_field`
    bucket. The value is typed per the parent state schema's `target_field` /
    `errors_field`; the representation is implementation-defined. Unused for `in_flight` and
    `not_started`.
  - `result_is_error` — boolean discriminator for `completed` entries: `true` when the
    contribution is a `collect`-mode error entry that rolls forward into `errors_field`,
    `false` when the contribution is a success value that rolls forward into
    `target_field`. MUST be `false` for `state in {"in_flight", "not_started"}` (the value
    of `result` is also unused in those states). Implementations MUST consult this field
    on resume to route the rolled-forward contribution; inferring routing from `result`
    shape is not permitted.
  - `completed_inner_positions` — for `in_flight` entries, a list of `NodePosition` entries
    with the same shape as `CheckpointRecord.completed_positions` (the outer-graph contract
    from §10.2), but scoped to this fan-out instance's inner subgraph execution rather than
    the outer graph. Empty when the instance is `in_flight` but no inner node has yet
    completed within this instance's subgraph (e.g., a sibling-triggered save fired right
    after this instance's first `started` event). Unused for `completed` and `not_started`.

**Count drift on resume.** When the engine loads a saved record and finds a
`fan_out_progress` entry whose `instance_count` does NOT equal the count the resumed run
resolves for the same fan-out node (per §9 `count` or `items_field` mode), the engine
MUST raise `checkpoint_record_invalid` (per §10.10). Implementations MUST NOT silently
pad the saved `instances` list with `not_started` entries when the resumed count is
larger, nor silently truncate trailing entries when the resumed count is smaller —
per-instance accumulator contributions written under one `instance_count` cannot be
reconciled with a different count without risking dropped or duplicated entries at the
fan-in step, breaking §10.11.1's exactly-once reducer guarantee. The check MUST happen
before any fan-out instance work runs on the resumed path; a saved record with multiple
fan-out entries raises on the first mismatch encountered. Users who intentionally change
a fan-out's input set between runs MUST start a fresh invocation rather than resume.

`completed` is the load-bearing state. An instance's `completed` status MUST mean: the
instance produced its durable contribution to the fan-out accumulator AND that contribution
is reflected in the entry's `result` field on the saved record. The contribution is
path-agnostic — a success result for the `target_field` bucket, or in `collect` error_policy
mode (per §9.5), a recorded error for the `errors_field` bucket. (`fail_fast`-mode failures
do NOT produce a `completed` state — the whole fan-out aborts in that mode.) The atomicity
contract is that the engine's "produce contribution + record into accumulator + save"
sequence MUST be ordered such that a crash between contribution and save leaves the
instance in `in_flight` state on the saved record (so resume re-runs it). A crash after the
save has succeeded is reflected as `completed`, the instance is skipped, and its
accumulator entry rolls forward to the fan-in step at fan-out completion. This is the same
correctness model as the rest of §10 — work that hadn't been recorded as saved at crash
time re-runs on resume.

#### 10.11.1 Reducer interaction

Per §9.3, fan-out results are merged into parent state via the parent's reducer for the
`target_field` (with reducer definitions per graph-engine §2). Per-instance resume
preserves the reducer's effect — the accumulator entries for `completed` instances roll
forward and are merged exactly once at the fan-out's fan-in step:

- `last_write_wins` — each `completed` instance has its result entry in the accumulator. At
  fan-in, the reducer merges entries in instance-index order, with the last instance's value
  winning. On resume, `completed` instances retain their original accumulator entries.
  Re-running a `completed` instance would record a SECOND accumulator entry; under §5
  determinism the values match, but the redundant entry is wasted work. Skipping is correct.
- `append` — each `completed` instance has its result entry in the accumulator. At fan-in,
  the reducer appends each entry to the target list in instance-index order. Re-running a
  `completed` instance would record a SECOND accumulator entry, causing a double-append at
  fan-in. Skipping is required for correctness.
- `merge` — each `completed` instance has its result entry in the accumulator. At fan-in,
  the reducer merges each entry into the dict-shaped outer field. Re-running a `completed`
  instance would record a second accumulator entry; for pure `merge` semantics this is
  idempotent but redundant. Skipping is correct and avoids the redundant work.

The `append` reducer case is why per-instance resume cannot be a "best-effort, may
double-contribute" model. The `completed` status is a correctness guarantee that there is
exactly one accumulator entry per instance heading into the fan-in step.

#### 10.11.2 Composition with `error_policy`

Per §9.5, fan-out has two error policies:

- **`fail_fast`.** A failed instance cancels its in-flight siblings; the fan-out raises. On
  resume after a `fail_fast` cancellation: the previously-failed instance is in `in_flight`
  state on the saved record (its terminal inner node fired `completed` with an error
  outcome — per graph-engine §6 every node attempt emits exactly one `completed` event —
  but `fail_fast` aborts before any accumulator entry is recorded for the failed slot, so
  the instance's `fan_out_progress` state is not promoted to `completed`). The
  previously-cancelled siblings are also in `in_flight` or `not_started` state. All of these re-run on resume per §10.7. Instances that had
  completed and merged before the failure remain `completed` and are skipped.
- **`collect`.** The fan-out runs all instances regardless of individual failures; failed
  slots are recorded in `errors_field` at the fan-in step. On resume, instances marked
  `completed` are skipped — their accumulator entry, either a success result for
  `target_field` or a recorded error for `errors_field`, is preserved and rolls forward to
  the fan-in step at fan-out completion. Instances in `in_flight` or `not_started` re-run;
  if they fail again, the failure is again recorded into the accumulator as an error entry.
  The `result_is_error` field on the saved per-instance entry (per §10.11) discriminates
  the two cases: `result_is_error: true` routes the contribution to `errors_field`;
  `result_is_error: false` routes it to `target_field`. Implementations MUST consult this
  field rather than inferring routing from `result` shape.

#### 10.11.3 Composition with `instance_middleware`

Per §9.7, `instance_middleware` (notably retry) wraps each instance's whole subgraph
invocation as a unit. Per-instance resume composes with retry middleware as follows:

- An instance whose retry middleware exhausted in `fail_fast` mode aborts the whole
  fan-out; the instance's `fan_out_progress` state at save time is `in_flight` (no
  accumulator entry was recorded — the failure cancelled the rest of the fan-out before any
  instance could save its `completed` state for the failed instance). All instances re-run
  on resume.
- An instance whose retry middleware exhausted in `collect` mode produces a recorded error
  entry in the accumulator. If a save fires after the error record (triggered by a
  sibling's `completed` event or by the fan-out's own completion), the instance's state is
  `completed` and its accumulator `result` field holds the error entry. On resume, the
  instance is skipped — the error contribution rolls forward to the fan-in step. If no save
  captured the error before the crash, the state reads as `in_flight` and the instance
  re-runs (potentially producing a different outcome the second time).
- On resume of an `in_flight` retry-exhausted instance, the instance re-runs with
  `attempt_index` reset to `0` per §10.6 — the retry budget restarts. This matches the
  "fresh execution attempt" semantics of resume.
- An instance whose retry middleware succeeded mid-run (e.g., attempt 2 of 3 succeeded)
  saved its `completed` state at the success (with the success result in its accumulator
  entry). On resume, that instance is skipped — the retry history is not preserved, but
  the result is.

#### 10.11.4 Configurable batching for fan-out internal saves

Fan-out internal saves (per §10.3) can be high-volume in workloads with many instances and
many inner nodes per instance. To keep the cost manageable, Checkpointer backends MAY
support **configurable batching** scoped specifically to fan-out internal saves. The
configuration is per-Checkpointer-instance and implementation-defined (per-language
ergonomics: a constructor parameter, a builder method, etc.). The behavioral contract:

- The configuration knob applies ONLY to fan-out instance internal `completed` events
  (saves triggered per §10.3 from inside a fan-out instance). It does NOT apply to
  outermost-graph saves, subgraph-internal saves, or the fan-out node's own completion
  save — those remain synchronous per §10.3 because they are correctness-critical for
  resume.
- When batching is enabled, the backend MAY buffer fan-out internal saves and flush them
  at configured intervals (count-based, time-based, or both). The buffered saves represent
  the most recent state of in-flight fan-out instances.
- When the fan-out completes (the engine fires the fan-out node's own `completed` event),
  the backend MUST flush all buffered fan-out internal saves before the fan-out node's
  save returns. This guarantees that the fan-out's success state is durably recorded
  before the engine proceeds.
- A crash with buffered-but-unflushed fan-out internal saves loses those buffered records.
  On resume, instances whose `completed` state was buffered-only re-run (the saved record
  reflects the most recent flushed state). This is acceptable because re-running a
  completed instance under per-instance resume's correctness rules requires a fresh
  contribution: an instance whose `completed` status was lost reverts to `in_flight` or
  `not_started` and the reducer rules in §10.11.1 still apply (the instance contributes to
  outer state for the first time on resume).

The cost trade-off is explicit: batching trades fewer durable writes per fan-out instance
for some redundant re-execution on crash recovery. Backends document their batching
defaults and configuration shape; users opt in with eyes open.

Default behavior is **no batching** (every fan-out internal save is synchronously
durable), to preserve the simplest correctness story for users who do not yet understand
their workload's cost profile.

### 10.12 State migrations

#### 10.12.1 Migration registration

A compiled graph MAY register zero or more **state migrations**. Each migration is described
by three pieces:

- `from_version` — the `schema_version` identifier the migration accepts as input.
- `to_version` — the `schema_version` identifier the migration produces as output.
- A **migration function** that, given a serialized state representation at `from_version`,
  returns a serialized state representation at `to_version`. The serialized form is whatever
  shape the active Checkpointer round-trips (per §10.1's "backends pick their own
  serialization"); the framework SHOULD pass the migration the most-deserialized form that is
  still independent of the current state class (e.g., a plain dict in Python, an
  `unknown`-shaped object in TypeScript) so the migration is not constrained by the user's
  current state-class definitions.

Migration support requires the active Checkpointer to be able to expose a structural
intermediate form of the loaded state (a plain dict, a JSON tree, or similar) that is
independent of the current state class definition. Backends using JSON, msgpack, or similar
schema-independent encodings naturally satisfy this; the SQLiteCheckpointer reference
implementation (per §10.13) does so by default. Backends using class-bound serialization
(Python pickle of state class instances) or live in-memory references to typed state objects
(the InMemoryCheckpointer reference implementation) cannot expose a class-independent
intermediate. When such a backend encounters a version mismatch on load AND one or more
migrations are registered, it MUST raise `checkpoint_record_invalid` per §10.10 with the
version mismatch in the error description; the migration registry has no opportunity to
bridge versions in that case. Implementations MUST document whether their Checkpointer
backend supports state migration.

The registration surface is per-language ergonomic. Python implementations are expected to
expose this on `GraphBuilder` (e.g., `with_state_migration(...)`); TypeScript implementations
may expose it on the builder or as a configuration object. The registration concept is what
this section mandates: migrations are bound to the compiled graph and consulted during
checkpoint load.

A compiled graph's migration set is **ordered by `(from_version, to_version)` pair**. The
order of registration does not affect chain resolution; chains are resolved by version pair,
not by registration order. Two migrations with the same `from_version` and same `to_version`
MUST raise `checkpoint_state_migration_chain_ambiguous` (per §10.10) at registration or
compile time, before any resume attempt. Two migrations with the same `from_version` and
different `to_version` define a branched migration graph; chain resolution (§10.12.2) is
responsible for picking a path.

#### 10.12.2 Chain resolution

When `Checkpointer.load(invocation_id)` returns a record whose `schema_version` does not
match the current state schema's `schema_version`, the engine MUST attempt to resolve a
**migration chain** from the record's version to the current version using the graph's
registered migrations.

Chain resolution proceeds:

1. Build a directed graph over registered migrations: each migration is an edge from its
   `from_version` to its `to_version`.
2. Find the shortest path (fewest edges) from the record's `schema_version` to the current
   state schema's `schema_version`. Implementations MUST resolve by shortest-path (BFS is
   the natural algorithm). When multiple distinct shortest paths exist (same edge count,
   different edge sequences), this is an ambiguous chain and the engine MUST raise
   `checkpoint_state_migration_chain_ambiguous` (per §10.10). The user MUST restructure
   their migration graph to leave a single canonical shortest path between every reachable
   version pair. Implementations SHOULD detect ambiguity at compile time when feasible (by
   scanning the registered migration graph); load-time detection is acceptable when
   compile-time analysis is not.
3. If at least one path exists, apply the migrations along the path in order: each
   migration's output becomes the next migration's input. The final serialized state is
   passed to the current state class's deserialization step (per §10.1 round-trip integrity).
4. If no path exists, raise `checkpoint_state_migration_missing` (per §10.10).

If a migration function itself raises during step 3 (chain application), the engine MUST
wrap the raised exception as `checkpoint_state_migration_failed` (per §10.10) and propagate
it to the caller. The migration's exception is preserved as the cause per the language's
idiom (`__cause__` in Python). Subsequent migrations in the chain MUST NOT run; the engine
abandons the chain at the failing migration and the resume attempt fails as a whole.

Migrations MUST be pure functions of their input (no I/O, no implicit state, deterministic
output for a given input). The framework does not enforce purity — users who violate the
contract risk non-deterministic resume, but the contract mirrors §10.5's idempotency stance:
documented, not policed. The engine MAY consult the migration registry multiple times during
a single resume — for example, when subgraph parent states (§10.2 `parent_states`) also need
migration. Implementations MUST apply the same chain resolution to each parent-state entry;
in the absence of per-parent version metadata, parent states MUST be treated as carrying the
same `schema_version` as the outer record. (A future proposal may add per-parent versioning
if subgraph state schemas evolve independently of the outer schema; for now the outer
record's `schema_version` is authoritative.)

#### 10.12.3 No-op when versions match

When the loaded record's `schema_version` equals the current state schema's
`schema_version`, the engine MUST NOT consult the migration registry; the record is loaded
directly per §10.4. This is the common-case fast path and incurs no migration overhead.

#### 10.12.4 Composition with `checkpoint_record_invalid`

§10.10's `checkpoint_record_invalid` covers structural incompatibility a migration cannot
fix — e.g., the serialized record itself is corrupt, or the post-migration state fails the
current state class's deserialization. After a migration chain runs, if the final
deserialized state still raises `checkpoint_record_invalid`, that error propagates
unchanged. Migrations are an opportunity to *avoid* `checkpoint_record_invalid` on
schema-version mismatches; they are not a recovery mechanism for arbitrary record
corruption.

If no migrations are registered for a graph and a loaded record's `schema_version` does not
match the current schema, the engine MUST raise `checkpoint_state_migration_missing`, NOT
`checkpoint_record_invalid`. Distinguishing the two categories matters: the former is
actionable ("register a migration"); the latter is not ("the record is broken").

### 10.13 Reference implementations and backend layering

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

### 10.14 Composition with sessions

Sessions (sessions §3 *Identity scoping*) are a sibling persistence layer keyed on a
caller-supplied `session_id`, with cross-invoke lifetime. Checkpointing and
sessions are orthogonal: an invocation MAY use both, neither, or either independently. They
MAY share a backend store, but the semantics are distinct — checkpoints capture per-invocation
progress for crash recovery and resume; session records carry per-session typed state that
survives across separate `invoke()` calls.

Composition rules:

- Both layers register independently on the compiled graph; a registered `Checkpointer` does
  NOT imply a `SessionStore` and vice versa.
- Resume (§10.4) and session load (sessions §6.1) are independent operations: resuming an
  invocation reloads its checkpoint record; binding to a session reloads the session record.
  Both MAY happen on the same `invoke()`.
- A `session_save_failed` (sessions §10) does NOT signal a checkpoint failure and vice versa;
  the error categories are distinct and surface independently.

### 10.15 Composition with suspension

The suspension capability (suspension §3 *The `suspend` operation*) uses the same persistence
mechanism as checkpointing for storing **paused-invocation records** (the persisted state of an
intentionally-suspended invocation: serialized state, signal descriptor per suspension §4,
`invocation_id` / `correlation_id`, and `completed_positions`). Implementations MAY use a single
backend store with a discriminator field distinguishing checkpoint records from paused-invocation
records, or separate stores. The spec treats them as distinct record types with overlapping
persistence requirements.

Composition rules:

- **Record-type distinction.** Checkpoint records (per §10.2) and paused-invocation records (per
  suspension §2) are distinct record shapes. The discriminator (or the separate-stores choice)
  is implementation-defined; the spec requires only that resume operations load the correct
  record type per the resume API in use (`invoke(resume_invocation=...)` per §10.4 loads a
  checkpoint record; `invoke(resume_invocation=..., signal_payload=...)` per suspension §7 loads
  a paused-invocation record).
- **Independent registration.** An invocation MAY use both, neither, or either capability
  independently. Registering a `Checkpointer` on the compiled graph enables checkpointing but
  does NOT enable suspension; the suspension capability's `suspend()` operation depends on the
  same persistence machinery being available but is invoked from the node body, not enabled by
  configuration.
- **Paused-record lifetime is not bound to invocation completion.** Unlike checkpoint records
  (which MAY be deleted on invocation completion per §10.2's lifecycle), a paused-invocation
  record persists until either (a) the invocation resumes and runs to completion, at which point
  the record MAY be deleted per backend policy, or (b) the application explicitly deletes the
  record (cancellation; backend-defined operation), or (c) backend-defined retention expires.
- **Error categories are distinct.** A `suspension_persistence_failed` (suspension §9) does NOT
  signal a checkpoint-save failure and vice versa; the error categories surface independently.

For the full suspension primitive (suspend operation, signal descriptors, suspended outcome,
signal payload merge, resume API, composition with sessions / subgraphs / fan-out /
parallel-branches / middleware, error categories), see the suspension capability spec.

## 11. Parallel branches

A **parallel branches** node holds a mapping from branch name to **branch spec** (§11.1.1).
At dispatch time, the engine projects parent state into each branch's per-branch state via
`inputs`, runs all branches concurrently (with optional per-branch middleware), and projects
each branch's exit state back into parent state via `outputs`. Different branches MAY write
different parent fields; when two branches write the same parent field, the parent's
reducer for that field merges the contributions per its semantics.

Parallel branches complements §9 fan-out. Fan-out is **data-driven**: N items, one
subgraph, instantiated N times. Parallel branches is **topology-driven**: M heterogeneous
compiled subgraphs, declared statically, run concurrently within a single parent invocation.

### 11.1 Configuration

A parallel-branches node carries:

- `branches` — a mapping from `branch_name` (non-empty string) to a **branch spec** (§11.1.1).
  Insertion order is preserved and is the order observer events for branch dispatch fire,
  regardless of completion timing (§11.8).
- `error_policy` — one of `"fail_fast"` (default) or `"collect"`. Same semantics as §9.5.
- `errors_field` — optional parent state field name receiving per-branch errors when
  `error_policy: "collect"`. Implementation-defined record shape; SHOULD include the failing
  `branch_name` and the error category.

#### 11.1.1 Branch spec

Each branch spec carries:

- `subgraph` — a compiled subgraph reference. Different branches MAY reference different
  compiled subgraphs with different state schemas.
- `inputs` — optional mapping `subgraph_field → parent_field` (same shape as the §4
  subgraph `inputs`). At branch entry, each named subgraph field is initialized from the
  named parent field. Subgraph fields not in `inputs` use the subgraph's declared defaults.
- `outputs` — optional mapping `parent_field → subgraph_field` (same shape as the §4
  subgraph `outputs`). At branch exit, each named parent field receives the named subgraph
  field's exit value, merged via the parent's reducer for that field.
- `middleware` — optional list of middlewares wrapping the whole branch invocation as a unit
  (§11.7). Heterogeneous across branches — branch A's middleware MAY differ from branch B's.

### 11.2 Per-branch projection (in)

At dispatch entry, each branch's initial subgraph state is constructed by:

1. Starting from the branch's subgraph schema's declared field defaults.
2. Overlaying `inputs` mappings: each subgraph field named on the LHS is set to the value of
   the corresponding parent field on the RHS, read from the parent state at dispatch time.

The mapping is the same shape as §4's subgraph `inputs`. References to undeclared subgraph
fields or undeclared parent fields are compile-time errors per §4's
`mapping_references_undeclared_field` category.

### 11.3 Concurrent execution

All branches dispatch simultaneously when the engine enters a parallel-branches node. This
is the second exception to graph-engine §3's single-threaded execution rule (alongside §9
fan-out's first exception); single-threaded execution resumes for the parent run after the
parallel-branches node completes.

This section does NOT include a configurable concurrency bound. The number of branches M
is expected to be small (typically 3–10), and per-branch concurrency tuning is rare in
practice. A future proposal MAY add a `concurrency` knob if real workloads demonstrate the
need.

### 11.4 Per-branch projection (out)

When a branch's subgraph finishes (END node reached), the engine constructs a per-branch
**contribution** — a mapping `parent_field → exit_value` built from the branch's `outputs`
mapping (each named subgraph field is read from the branch's exit state). Subgraph fields
not named in `outputs` are discarded (matching §4 outputs semantics).

Contributions are **buffered**; no parent-state merging happens incrementally on branch
completion. When the parallel-branches node itself completes (all branches succeeded under
`fail_fast`, or `collect` ran to completion), the engine applies all buffered contributions
to parent state in **branch insertion order** (§11.8), using each parent field's reducer
for that field. This mirrors §9.3 fan-in: contributions are collected during dispatch and
merged deterministically once at node completion.

When two or more branches write the same parent field via `outputs`, the parent's reducer
applies the contributions in branch insertion order. For `last_write_wins` reducers, this
means the last-listed branch wins. For `append` reducers, contributions are appended in
branch order. For `merge` reducers, later branches' keys override earlier ones.

Authors choosing parent fields and reducers SHOULD design for the merge semantics they
want. A common pattern is using `merge` for fields multiple branches contribute to (each
branch writes its own keys) or `last_write_wins` with branches that write disjoint fields.

### 11.5 Error policy

Same shape as §9.5. Behavior at runtime:

- **`fail_fast` (default).** First branch failure cancels every still-running branch (via
  the host language's idiomatic cancellation primitive — Python `asyncio.Task.cancel()`,
  TypeScript `AbortController`, etc.). The parallel-branches node raises a wrapped
  `node_exception` carrying the failing branch's exception as `__cause__`. Per §11.4's
  collect-then-apply semantics, no branch contributions have been applied to parent state at
  this point; the buffered contributions are discarded. `recoverable_state` is therefore the
  parent state at the moment the parallel-branches node entered — matching §9.5's fan-out
  fail_fast.
- **`collect`.** All branches run to completion regardless of individual failures.
  Successful branches' contributions merge per §11.4. Failed branches' errors are recorded
  in `errors_field` (when configured); their `outputs` projections do NOT fire. The node
  returns normally; the parent run continues.

Implementations MAY surface partial-completion telemetry (which branches succeeded, which
failed) via observer events (graph-engine §6).

### 11.6 Composition with parent middleware

Per-graph and per-node middleware applied to the parallel-branches node wrap it as a SINGLE
dispatch — exactly mirroring §9.6's contract for fan-out. From the parent's middleware
view, the parallel-branches node looks like any other node: one `started` event, one
`completed` event around the whole operation. The parent's retry middleware, if any,
retries the whole parallel-branches node (re-dispatching all M branches), not individual
branches.

Per-branch internal events (the branches' subgraph nodes' started/completed pairs) come
from the branches' subgraph executions and carry the new `branch_name` field (§11.7,
graph-engine §6).

### 11.7 Branch middleware

Each branch's `middleware` (§11.1.1) wraps the branch's entire subgraph invocation as a
unit — directly mirroring §9.7's `instance_middleware` contract. The branch's whole
subgraph runs inside the middleware chain; failures in any inner node propagate up to the
branch's middleware. Retry middleware applied at the branch level retries the whole
branch's subgraph.

Branch middleware composition is heterogeneous. Branch A may have `[retry, timing]`; branch
B may have `[]`; branch C may have `[custom_breaker]`. Each branch's chain is independent.

### 11.8 Determinism

The branch dispatch order — and therefore the order branches' `started` events fire on the
graph-engine §6 observer stream — is the **insertion order of the `branches` mapping**.
This holds regardless of which branch's first inner node finishes first.

Branch fan-in (§11.4) is deterministic: when two branches write the same parent field, the
reducer applies their contributions in branch insertion order, not completion order.

This preserves graph-engine §5's "same input → same output" determinism guarantee through
the parallel-branches primitive: scheduler nondeterminism affects timing but not state.

### 11.9 Errors

New canonical categories:

- `parallel_branches_no_branches` — compile-time error. The `branches` mapping is empty.
  Non-transient.
- `parallel_branches_branch_failed` — runtime category. Raised by the engine when a
  branch's subgraph raises under `error_policy: "fail_fast"`. Wraps the inner exception as
  `__cause__`; carries the failing `branch_name` as a structured field. Non-transient by
  default; inherits transient classification from the wrapped exception per §6.1.

Existing categories that compose:

- `mapping_references_undeclared_field` (§4) — raised at compile time when an `inputs` or
  `outputs` mapping in a branch spec names a field not declared on the relevant side.
- `node_exception` (graph-engine §4) — the `parallel_branches_branch_failed` category is a
  `node_exception` subtype attached at the parallel-branches node's level.

Composition with §10 checkpointing: the parallel-branches node fires graph-engine §6
events that the §10 Checkpointer captures per its existing rules. Atomic-restart semantics
apply to parallel branches: a crash mid-dispatch re-runs the whole parallel-branches node
on resume. Per-branch resume (the analogue to fan-out's per-instance resume in §10.7) is
deferred to a follow-on; the parallel-branches primitive does not yet populate a per-branch
progress field on the checkpoint record.
