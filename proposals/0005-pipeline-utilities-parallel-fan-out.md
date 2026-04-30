# 0005: Pipeline Utilities — Parallel Fan-Out

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-04-28
- **Accepted:** 2026-04-28
- **Targets:**
  - spec/pipeline-utilities/spec.md (extends; adds new §9 "Parallel fan-out" after the existing §8 Out of scope; modifies §6.1 Retry middleware to remove the now-redundant manual dispatch of failed-attempt events)
  - spec/graph-engine/spec.md (modifies §3 Execution model — fan-out concurrency exception; modifies §6 Observer hooks — replaces single-event-per-attempt model with **started/completed pairs**, adds per-observer phase-subscription filter, adds `fan_out_index` field, removes the "Middleware-dispatched events" subsection that v0.5.0 added since it is no longer needed under the pair model)
- **Related:** 0001, 0003, 0004
- **Supersedes:**

## Summary

Add a parallel fan-out primitive to pipeline-utilities: a `FanOutNode` that runs a compiled subgraph
(or async callable) once per item in a parent state field, executing instances concurrently up to a
configurable bound, and merging results back into a parent collection field. Default error policy is
fail-fast (cancel siblings on first error); a `partial_failures` mode collects per-item failures
without raising. Updates graph-engine §3 to acknowledge fan-out as the single intentional
concurrency exception, and §6 to attribute observer events to a specific fan-out instance via an
optional `fan_out_index` field.

## Motivation

Concurrent batch processing of N items through the same logic is one of the two most common LLM
pipeline shapes — the other being deterministic single-pass pipelines (already covered by graph-
engine). Examples in the openarmature charter's case studies and the work projects that drive this
proposal:

- Score 200 retrieved documents through the same LLM-grading subgraph; collect all scores.
- Generate per-item summaries for a batch of input rows.
- Run the same agent loop across many user prompts in an evaluation harness.

Today, none of this is expressible inside a graph: graph-engine §3 mandates single-threaded
execution per invocation, and the user's only options are (a) write a synchronous loop that runs
each item serially (correct, but throws away per-item concurrency), (b) hand-roll an `asyncio.gather`
inside a node body (loses the engine's observability, retry, and projection facilities for the
inner work), or (c) use a graph-engine-external batch runner like `asyncio.gather(graph.invoke(s)
for s in inputs)` (works, but loses the parent's surrounding graph context and fan-in semantics).

A first-class fan-out primitive captures the pattern once and lets the rest of the framework see
into it:

- Each fan-out instance gets its own observer events with `namespace` chained through the fan-out
  node name and disambiguated by a per-instance index.
- Per-instance retry middleware (pipeline-utilities §6.1) wraps each instance independently.
- The fan-out node itself can carry middleware (e.g., concurrency limiting via a semaphore-style
  middleware, OTel instrumentation).
- Fan-in is structured: results are merged into a parent collection field via the parent's reducer,
  matching the existing subgraph projection contract.

## Detailed design

This proposal updates two specs. The pipeline-utilities update adds a new `Parallel fan-out`
section to that capability; the graph-engine updates carve out §3's concurrency rule and extend the
§6 event shape.

The spec versions under which these changes land are determined at acceptance time and recorded in
`CHANGELOG.md`.

---

### Pipeline-utilities §9: Parallel fan-out

Append the following section to `spec/pipeline-utilities/spec.md` after the current §8 Out of scope.
At v0.5.0 acceptance, pipeline-utilities runs §1–§8; this proposal adds §9.

#### 9. Parallel fan-out

A **fan-out node** is a special node type that executes a compiled subgraph (or async callable) once
per item in a designated parent state field, with instances running concurrently up to a
configurable bound, and collects per-instance results back into a parent collection field.

Fan-out nodes are the single place in the engine where multiple subgraph executions overlap in time
within a single invocation; everywhere else (graph-engine §3) execution is single-threaded.

##### Configuration

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
| `concurrency` | Optional. Upper bound on concurrently-running instances. Accepts either a literal `int` (static concurrency fixed at compile time), a callable `(state) -> int` (concurrency read from / computed over parent state at fan-out entry), or `None` (unbounded). Default: `10`. Same int-or-callable shape as `count` (§9.1) for symmetry. |
| `error_policy` | One of `"fail_fast"` (default) or `"collect"`. See §9.5 below. |
| `on_empty` | One of `"raise"` (default) or `"noop"`. Behavior when the resolved instance count is zero. `"raise"` (default) treats empty as unexpected and raises a `node_exception` per graph-engine §4 with category `fan_out_empty`. `"noop"` treats empty as a legitimate state and produces a silent no-op. See §9.1 below. |
| `count_field` | Optional. A field name on the parent state into which the fan-out writes the resolved instance count after execution. MUST be a declared int-typed field on the parent state schema. Useful for programmatic inspection of how many instances ran (e.g., a downstream conditional edge that branches on `state.count_field == 0`). Written at the fan-in step regardless of `on_empty` mode; if `on_empty: "raise"` and count is zero, the raise occurs before the field is written. |
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

##### 9.1 Per-instance projection

At fan-out entry, the engine snapshots the parent state and resolves the instance count and
per-instance state per the active mode:

**`items_field` mode.** For each item in the snapshot's `items_field`, an instance is constructed
with:

- `item_field` ← the item value
- For each `(subgraph_field, parent_field)` in `inputs`: subgraph field ← parent field's value at
  the snapshot
- All other subgraph fields ← schema defaults

Per-item items are assigned in input list order. Each instance is tagged internally with its
0-based index in the input list (`fan_out_index`); see §6 below.

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

When `on_empty: "noop"` is used and the user wants to react to the empty case programmatically,
the recommended pattern is to configure `count_field` and add a downstream conditional edge that
branches on the field value:

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

##### 9.2 Concurrent execution

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

##### 9.3 Per-instance fan-in

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

##### 9.4 Item ordering and fan-in determinism

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

##### 9.5 Error policy

`error_policy: "fail_fast"` (default):

- The first instance that raises causes the engine to cancel all sibling instances and propagate
  the original exception. Cancellation MUST be cooperative (the language's idiomatic cancellation
  signal: Python `CancelledError`, TypeScript `AbortSignal`); instances MUST be given the opportunity
  to clean up.
- The propagated exception is the offending instance's, wrapped in a `node_exception` per graph-
  engine §4. Recoverable state is the parent state at fan-out entry (the snapshot).
- Sibling cancellations DO NOT produce additional `node_exception` per cancelled instance;
  cancellations are infrastructure, not user-visible errors. Observers MAY see partial events from
  cancelled instances (whatever fired before cancellation propagated).

`error_policy: "collect"`:

- All instances run to completion (whether success or error).
- A successful instance contributes to fan-in normally.
- A failed instance contributes nothing to `target_field` (its slot is OMITTED — input order is
  preserved among successes).
- After all instances complete, fan-in merges successes; the engine then proceeds to the outgoing
  edge.
- Per-instance errors are recorded in a parent state field named by an additional config field
  `errors_field` (default: omitted, meaning errors are silently dropped after their per-instance
  events fire). `errors_field` MUST refer to a declared list-typed field with an extending reducer.

The `collect` policy never raises from the fan-out node itself; no exception is propagated even if
ALL instances fail. Users who need failure thresholds compose this with downstream conditional
edges over the `errors_field`.

##### 9.6 Composition with middleware

Per-graph and per-node middleware (pipeline-utilities §3) compose with fan-out as follows:

- **Per-graph middleware** wraps the fan-out node *as a single dispatch* — sees the input parent
  state, sees the merged-fan-in partial update on completion. Per-graph middleware does NOT see
  per-instance state.
- **Per-node middleware on the fan-out node itself** wraps the same dispatch; same scope as per-
  graph but applied only to this fan-out.
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

##### 9.7 Instance middleware

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
(per pipeline-utilities §6.1) and `fan_out_index` populated.

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
  one outermost middleware enter and one outermost middleware exit per fan-out execution. They do
  NOT see per-instance retries or per-instance failures (those are absorbed by
  `instance_middleware` if present).
- This means a per-graph timing middleware on the outer graph, with an `instance_middleware`
  retry around each instance, records *total elapsed time including all per-instance retries*. A
  per-graph timing middleware sees only the fan-out as a whole; per-instance attempts are
  invisible at that scope.

The `instance_middleware` chain MUST be the same for every instance in a single fan-out — there
is no per-item middleware variation. Heterogeneous per-item behavior remains out of scope (see
the Alternatives considered section in proposal 0005 for the rationale and pipeline-utilities §8
Out of scope for the deferred-feature list at the capability level).

---

### Graph-engine §3: Execution model (fan-out concurrency exception)

Replace the current paragraph in graph-engine §3 (after step 5):

> Execution is single-threaded per invocation: one node is active at a time within a given graph
> run. Parallel fan-out is a separate concern addressed by pipeline utilities (future capability),
> not by the base execution model.

with:

> Execution is single-threaded per invocation **except inside a fan-out node** (pipeline-utilities
> §9): one node is active at a time within a given graph run, with the bounded exception that a
> fan-out node may execute multiple subgraph instances concurrently. After a fan-out node
> completes, single-threaded execution resumes for the rest of the parent run.

### Graph-engine §6: Observer hooks (event pairs, phase filter, fan-out index attribution)

This proposal makes three coordinated changes to the §6 contract: it replaces the
single-event-per-attempt model (introduced in v0.5.0 / proposal 0004) with **started/completed
event pairs**, adds a per-observer **phase-subscription filter**, adds the `fan_out_index` field
for fan-out attribution, and removes the "Middleware-dispatched events" subsection (no longer
necessary). The combined design lands as a single coherent §6 update.

#### Started/completed pairs

Replace v0.5.0's "one event per node attempt" rule with: each node attempt produces **two events**
delivered in temporal order — a `started` event before the node executes, and a `completed`
event after the node returns or raises. The pair shares all attempt-identifying fields
(`node_name`, `namespace`, `step`, `attempt_index`, `fan_out_index`, `pre_state`,
`parent_states`); the differences are:

- `started` event: a new `phase: "started"` field. `post_state` and `error` MUST be absent.
- `completed` event: `phase: "completed"`. Exactly one of `post_state` or `error` MUST be
  populated, matching the v0.5.0 contract for the single completion event.

The two events are dispatched onto the same observer delivery queue and follow the same per-event
delivery rules (graph-attached outermost-to-innermost, then invocation-scoped); for a single
attempt, `started` is delivered before `completed`.

Add the new field to the §6 Node event shape:

> - `phase` — required, one of `"started"` or `"completed"`. `started` events are dispatched
>   before the node executes (after middleware pre-phases; right before the wrapped function
>   call). `completed` events are dispatched after the node returns or raises and the reducer
>   merge runs (or after the failure is captured, on failure). Each node attempt produces
>   exactly one `started` and exactly one `completed` event in that order.

The other §6 fields are unchanged. The pair-bracket model means `pre_state` is meaningful on both
events (state coming into the node); `post_state` / `error` are populated only on `completed`.

Replace the §6 "Event dispatch" subsection's opening with:

> **Event dispatch.** Each node attempt produces a started/completed event pair. The engine
> dispatches the `started` event before invoking the wrapped node function (after all middleware
> pre-phases run); the engine dispatches the `completed` event after the reducer merge succeeds
> (with `post_state` populated) or after the node, reducer, or state validation fails (with
> `error` populated). Both events are dispatched synchronously before proceeding to the next
> graph step.

#### Per-observer phase subscription

Observer registration (§6 Registration modes, both graph-attached and invocation-scoped) accepts
a new optional `phases` parameter — a set of phase strings the observer will receive. Accepted
values:

- `{"started", "completed"}` — both phases. **Default if `phases` is not specified.**
- `{"completed"}` — only `completed` events (matches v0.5.0's single-event-per-attempt
  observation pattern). Use for metrics aggregators, completion-only logs, retry-classification
  observers.
- `{"started"}` — only `started` events. Use for stuck-node detectors and "node entered"
  alerting.

Empty phase sets are not permitted — registering an observer that subscribes to nothing is a
configuration error and implementations SHOULD raise at registration time.

When delivering events, the engine MUST check the receiving observer's `phases` set before
dispatching the event to that observer; it MUST NOT deliver an event whose phase is not in the
subscribed set. Observers with different phase subscriptions on the same graph or invocation are
permitted and common — e.g., an OTel observer subscribes to both for span boundaries while a
metrics observer subscribes to `completed` only.

The phase filter applies at delivery, not dispatch — the engine still produces both events for
every attempt; observers that don't subscribe simply don't receive them. This keeps the §6
delivery-queue invariants and determinism guarantees intact regardless of observer mix.

#### Fan-out index field

Add to the §6 Node event shape:

> - `fan_out_index` — optional non-negative integer. Populated only for events from nodes that
>   execute inside a fan-out instance. The 0-based index of this fan-out instance among its
>   siblings (in `items_field` mode, matching the position of the corresponding item; in
>   `count` mode, `0..count-1`). When the same node name appears in multiple fan-out
>   instances, the combination of `namespace`, `fan_out_index`, and `attempt_index` uniquely
>   identifies the event source. Absent for events from nodes that are not inside any fan-out
>   instance.

A fan-out node itself produces a started/completed event pair (matching all other nodes), with
`fan_out_index` absent. Per-instance events have `fan_out_index` populated on both phases.

The §6 invariant `len(parent_states) == len(namespace) - 1` is preserved; fan-out does not extend
`namespace` beyond what subgraph composition already produces. Implementations MUST emit per-
instance events under a deterministic namespace based on the inner subgraph's node structure.

#### Removal of "Middleware-dispatched events"

The "Middleware-dispatched events" subsection added in v0.5.0 (proposal 0004) is REMOVED. Under
the pair model, the engine instruments at the inner-node-call level: each invocation of the
wrapped node function produces a started/completed pair from the engine. Retry middleware that
re-attempts produces multiple invocations, each of which the engine brackets independently —
no manual middleware dispatch is required.

The retry middleware's behavior in pipeline-utilities §6.1 is correspondingly simplified (see
"Pipeline-utilities §6.1: Retry middleware (manual dispatch removed)" below).

#### Determinism

The §5 determinism guarantee continues to apply with the natural extension to pairs: given the
same inputs and registered observers (with the same phase subscriptions), the sequence of
delivered events MUST be identical across runs. For each attempt, `started` is always delivered
before `completed` to every subscribed observer.

---

### Pipeline-utilities §6.1: Retry middleware (manual dispatch removed)

The pair-model change in graph-engine §6 makes retry's per-attempt observer events fall out of
the engine's own dispatch — every invocation of the wrapped node produces a started/completed
pair regardless of which middleware is wrapping the call. Retry no longer needs to manually
dispatch failed-attempt events. Two updates to pipeline-utilities §6.1:

#### §6.1 Behavior pseudocode

Replace v0.5.0's pseudocode:

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

with:

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

The `dispatch_failed_attempt_event` call is gone. Each call to `next(state)` triggers a fresh
engine-dispatched started/completed pair; the engine handles all observer events.

#### §6.1 Per-attempt observer events

Replace the v0.5.0 "Per-attempt observer events" subsection's content with:

> Each retry attempt produces a started/completed event pair from the engine (per graph-engine
> §6's pair model). Failed attempts have their `completed` event populated with `error`;
> successful attempts have `post_state`. The engine dispatches all events; retry middleware does
> NOT dispatch directly. Net result: 2N events for an N-attempt retry, with `attempt_index` values
> `0..N-1` in order. The first 2(N-1) events are pairs ending in `error`; the final two events
> are a pair ending in either `post_state` (success) or `error` (terminal failure).
>
> Observers that only need terminal outcomes (per-attempt completed events) MAY subscribe to
> `phases={"completed"}` per the §6 phase filter and skip the `started` deliveries entirely.

---

## Conformance test impact

This proposal touches conformance fixtures in two ways: it **adds new fixtures** (017-022 in
pipeline-utilities; 017-018 in graph-engine), and it **modifies existing v0.5.0 fixtures** to
match the new pair-event contract.

### Modified existing fixtures (v0.5.0 fixtures, updated in this proposal's accept PR)

The following v0.5.0 fixtures contain observer-event assertions that need updating from the
single-event-per-attempt model to the pair model:

- **`spec/graph-engine/conformance/012-observer-basic-firing`** — each event in the existing
  fixture splits into a `started` + `completed` pair. Default phase subscription is both.
- **`spec/graph-engine/conformance/013-observer-subgraph-namespacing-and-ordering`** — same.
- **`spec/graph-engine/conformance/014-observer-error-event`** — failing-node attempt now
  produces a `started` event followed by a `completed` event with `error` populated.
- **`spec/graph-engine/conformance/015-observer-error-isolation`** — same; observer raising on
  any phase event MUST NOT prevent subsequent events from being delivered.
- **`spec/graph-engine/conformance/016-observer-attempt-index-default`** — verifies `phase`
  is populated correctly on every event AND every attempt produces a started/completed pair
  (3 nodes → 6 events instead of 3).
- **`spec/pipeline-utilities/conformance/011-middleware-determinism`** — three retry attempts
  → 6 events (3 pairs) deterministically.
- **`spec/pipeline-utilities/conformance/015-retry-per-attempt-observer-events`** — three
  attempts → 6 events; retry middleware does NOT manually dispatch (engine handles all).

### New fixtures: pipeline-utilities (017-023)

Seven new fixtures under `spec/pipeline-utilities/conformance/`. The pipeline-utilities
conformance dir runs 001-016 at v0.5.0 (with the updates above); this proposal adds 017-023.

17. **`017-fan-out-basic`** — parent state has `items: list[int] = [1, 2, 3]` and
    `results: Annotated[list[int], append] = []`. Fan-out node runs an inner subgraph that doubles
    the item. Verifies:
    - Three instances run.
    - Final `results == [2, 4, 6]` (input order preserved despite concurrent completion).
    - Observer events for inner-subgraph nodes come as started/completed pairs and carry
      `fan_out_index` 0, 1, 2 on both phases.
    - The fan-out node itself produces a started/completed pair (with `fan_out_index` absent).
    - Outer execution order shows the fan-out node treated as a single step.

18. **`018-fan-out-fail-fast`** — fan-out where instance index 1 raises. Verifies:
    - The fan-out node propagates the exception as `node_exception` per graph-engine §4.
    - Recoverable state matches the pre-fan-out snapshot.
    - Sibling instances are cancelled (their final-state events do NOT fire as
      `post_state`-populated; the events that DO fire from cancelled instances carry the language's
      cancellation marker — Python `CancelledError`).

19. **`019-fan-out-collect`** — fan-out with `error_policy: "collect"` and `errors_field`. Two
    instances succeed, one raises. Verifies:
    - Final `target_field` carries the two successful values, in input order, with the failed
      instance's slot omitted.
    - `errors_field` carries the recorded failure.
    - The fan-out node itself does NOT raise; downstream nodes execute normally.

20. **`020-fan-out-with-retry-middleware`** — fan-out where each instance has a retry middleware
    wrapping a flaky inner node. Verifies:
    - Each instance retries independently.
    - Sibling instances are not delayed by another instance's retries beyond the concurrency budget.
    - Final state reflects all instances eventually succeeding.
    - Per-attempt event pairs from inner instances carry both `attempt_index` and `fan_out_index`
      populated on both phases. For each retry attempt, the engine dispatches a started/completed
      pair (2 events per attempt); a 3-attempt retry across 3 instances produces 18 events total.
      Retry middleware does NOT manually dispatch.

21. **`021-fan-out-with-instance-middleware-retry`** — fan-out where `instance_middleware: [retry]`
    wraps each instance's whole subgraph invocation. Inner subgraph has multiple nodes, and the
    failure surfaces from a node that node-level retry alone could NOT have handled (e.g., an
    error mid-flow that requires re-running prior nodes too). Two sub-cases:
    - `instance_middleware_retry_succeeds` — instance fails on first whole-invoke (transient),
      succeeds on second whole-invoke. Final state reflects the eventual success; the inner
      subgraph re-runs from scratch on retry (fresh state, every node re-executes).
    - `instance_middleware_retry_exhausts_then_fail_fast` — instance exhausts retries; under
      `error_policy: fail_fast`, sibling instances are cancelled, and the engine surfaces a single
      `node_exception` per §4.

22. **`022-fan-out-count-and-concurrency-modes`** — fan-out using `count` instead of `items_field`,
    and exercising both static and callable forms of the `count` and `concurrency` parameters.
    Four sub-cases:
    - `count_literal` — `count: 3`. Three instances run; each starts with subgraph schema
      defaults plus any `inputs` mapping; no `item_field` projection. Collected results are an
      ordered list of three values.
    - `count_callable_from_state` — `count: lambda state: state.worker_count` where parent state
      has `worker_count: int = 4`. Four instances run.
    - `count_callable_computed` — `count: lambda state: max(1, len(state.queue) // 10)` where
      parent state has `queue: list[str]` with 35 elements. Three instances run (35 // 10 = 3,
      max with 1).
    - `concurrency_callable_with_items_field` — `items_field` mode with 6 items;
      `concurrency: lambda state: state.allowed_in_flight` where state has `allowed_in_flight:
      int = 2`. Six instances run total but with no more than 2 concurrent; the harness verifies
      the "at most 2 in flight" invariant via per-instance entry/exit timing markers.
    Verifies that `item_field` is correctly absent in count modes, `fan_out_index` values run
    `0..count-1`, `target_field` is collected in instance-index order, and dynamic concurrency
    is resolved once at fan-out entry from parent state.

23. **`023-fan-out-empty-input`** — verifies the empty-input no-op semantics across both modes
    via three sub-cases:
    - `items_field_empty` — `items_field == []`. Zero instances run; `target_field` unchanged;
      `errors_field` (if configured) unchanged; fan-out node fires a started/completed pair with
      `post_state` reflecting the no-op. Downstream node runs normally.
    - `count_literal_zero` — `count: 0`. Same outcome: zero instances, no-op, downstream runs.
    - `count_callable_returns_zero` — `count: lambda state: 0`. Same outcome.
    Verifies no implementation raises, observer events fire correctly, and the graph completes
    normally despite the empty input.

The conformance harness supplies a deterministic mock-flaky-node adapter for fixture 020 and a
deterministic mock-flaky-instance adapter for fixture 021; real-time-dependent jitter is swapped
for a fixed sequence in both.

### New fixtures: graph-engine (017-018)

Two new fixtures under `spec/graph-engine/conformance/`. The graph-engine conformance dir runs
001-016 at v0.5.0 (with the updates noted above for the pair model); this proposal adds 017-018.

- **`017-observer-fan-out-index`** — graph with a fan-out node; verifies:
  - Per-instance events come as started/completed pairs and carry `fan_out_index` matching their
    input list index on BOTH phases.
  - The fan-out node's own pair has `fan_out_index` absent on both phases.
  - Events from nodes outside the fan-out have `fan_out_index` absent.
  - Per-instance events also carry `attempt_index == 0` (no retry middleware in this fixture);
    the combination of `namespace`, `fan_out_index`, `attempt_index`, and `phase` uniquely
    identifies each event.

- **`018-observer-phase-subscription`** — a linear three-node graph with three observers
  registered, each with a different phase subscription:
  - `obs_both` (no `phases` parameter — defaults to both): receives 6 events (3 nodes × 2
    phases).
  - `obs_completed` (`phases={"completed"}`): receives 3 events (one per node, completed only).
  - `obs_started` (`phases={"started"}`): receives 3 events (one per node, started only).
  - All three observers see events in delivery-order interleaved consistently (same `step` and
    `node_name` correlations); none receives an event whose phase is not in its subscription.
  - Observer registered with empty `phases` set raises a configuration error at registration
    time.

---

## Alternatives considered

**Do nothing — let users write `asyncio.gather` inside a node body.** Works for ad-hoc cases but
loses the engine's observability, projection, and middleware integration for the inner work.
Per-item events don't appear in the observer stream. Per-instance retry has to be re-coded inside
the node. Rejected because the use case is too central to LLM pipelines (every batch-processing
shape lands here).

**Multiple parallel `add_edge` outputs from a single node.** A node could fan out by declaring
multiple successors; each runs concurrently. Rejected: this conflicts with graph-engine §2's
"each node has exactly one outgoing edge" rule (a deliberate choice to make routing logic
inspectable). Re-litigating that rule is outside scope. Fan-out is a different shape — same logic
N times — and deserves a different primitive.

**Treat fan-out as a higher-order subgraph (a subgraph whose entry node is implicitly a parallel
loop).** Cleaner conceptually but requires a new entry-node concept and changes the graph-engine
§2 model in a non-additive way. Rejected as too invasive for what amounts to a pipeline-utilities
concern.

**Heterogeneous fan-out (different subgraphs per item).** Useful for A/B routing inside a fan-out.
Deferred — uncommon; users can express it today by switching on the item inside a uniform
subgraph.

**Streaming fan-in (downstream nodes see partial results as instances complete).** Useful for
"first N results, cancel rest" patterns. Deferred to a follow-on streaming proposal. The current
fan-in waits for all instances before merging.

**Implicit fan-out via list-typed projections.** A subgraph node whose `inputs` mapping receives a
list-typed parent field could implicitly fan out. Rejected because it conflates explicit-mapping
semantics (graph-engine §2 / proposal 0002) with concurrency semantics, making the user-facing
contract harder to reason about. Explicit `FanOutNode` keeps the two concerns separate.

**Default `concurrency: None` (unbounded).** Rejected — unbounded fan-out hits provider rate limits
hard and tends to OOM on large item lists. The default `10` is a sensible starting bound that
covers most cases without adversarial concurrency. Users who need higher throughput compose with
the rate-limiting capability (future) or override.

**Default `error_policy: "collect"`.** Rejected because silent partial failures are a debugging
nightmare in pipelines; users who want partial-failure semantics opt in explicitly. The default
fail-fast surfaces problems immediately.

**Per-instance independent state including parent-snapshot views.** Currently the parent snapshot
is taken once at fan-out entry and shared. An alternative would let each instance see a "current"
parent state (which would require synchronization). Rejected — instances are independent by
design; shared mutable parent state would require locks and break determinism.

**Bake fan-out into the subgraph projection.** A subgraph could declare itself "fan-outable" and
then `add_subgraph_node` would handle fan-out implicitly. Rejected for the same reasons as the
list-typed-projection alternative: conflates two contracts.

## Open questions

None at time of submission.
