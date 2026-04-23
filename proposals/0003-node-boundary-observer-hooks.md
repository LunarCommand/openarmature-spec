# 0003: Node-Boundary Observer Hooks

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-04-22
- **Accepted:**
- **Targets:** spec/graph-engine/spec.md (promotes §6 from informative to normative; minor cross-reference in §3)
- **Related:** 0001
- **Supersedes:**

## Summary

Specify a node-boundary observer hook on compiled graphs: a registered observer function is invoked once
per node execution with the node name, pre-update state, post-update state (or error), a step index, and
a subgraph namespace. Observers are read-only, fire in registration order, and cannot affect graph
execution. This promotes the informative note in §6 of the current graph-engine spec to a normative
specification.

## Motivation

Proposal 0001 §6 reserved an observability-hooks section but deferred its specification until "the base
execution model is stable." The execution model has been stable since v0.1.0 and refined in v0.1.1;
observability is the natural next piece. There are three reasons to land the observer hook before the
broader pipeline layer:

1. **Data-side / control-side asymmetry.** Today the engine supports one observability pattern: the
   `trace` field — nodes append to a list-typed reducer field, and the final state carries the history.
   That's the *data-side* pattern, and it falls out of existing State + reducer primitives. The
   *control-side* equivalent — external code observing execution as it happens — has no primitive. This
   leaves intermediate state inside subgraphs invisible to anything outside the graph: subgraph-internal
   fields that aren't projected back per §2 vanish after each merge, and the engine keeps no snapshot
   history.

2. **Foundational primitive for deferred capabilities.** Streaming outputs, checkpointing/resume, and
   human-in-the-loop interrupts (all listed in §7 Out of scope of the graph-engine spec) each need
   "where does the engine let external code observe?" answered before they can be spec'd. Landing the
   hook first means those later proposals compose on a stable seam rather than negotiating one ad hoc.

3. **Immediate user value.** With the hook in place, users can build observability integrations
   (Langfuse, structured logs, custom dashboards) today, without waiting for the pipeline layer to
   ratify. The hook's own surface area is small — a callback signature — which is far easier to design
   well than the larger features that would consume it.

## Detailed design

Promote §6 of `spec/graph-engine/spec.md` from informative to normative and replace its body with the
text below. Add one cross-reference to §3 Execution model so the hook's position in the step loop is
explicit.

### §6 Observer hooks (new body, normative)

The compiled graph MUST expose a way to register one or more **observers**. An observer is a function
or callable that receives a **node event** and returns nothing of interest to the engine. Observers
inspect execution as it happens; they MUST NOT alter state, routing, or any other aspect of the graph
run.

An implementation MUST support at least two registration modes:

- **Graph-attached.** Observers registered on a compiled graph fire on every invocation of that graph
  until removed.
- **Invocation-scoped.** Observers passed to a single invocation fire only for that invocation.

An implementation MAY provide additional registration modes; these two are the minimum.

Observers attached to a compiled graph fire whenever that graph runs — whether invoked directly by a
caller or as a subgraph inside a parent. A subgraph's attached observers therefore receive events for
the subgraph's internal nodes during a parent run, in addition to any observers attached to or passed
to the parent.

Observers MUST be asynchronous — the delivery queue awaits each observer to coordinate its
completion. In Python this means `async def` observers; in TypeScript, functions returning
`Promise<void>`. An implementation MAY accept synchronous observers by wrapping them internally, but
this specification models observers as async to keep delivery semantics well-defined.

**Event delivery.** Observer events are delivered asynchronously with respect to graph execution. The
graph's execution loop MUST NOT await observer processing; observer latency MUST NOT affect node
execution timing. Each invocation of the outermost graph has an observer delivery queue that runs
concurrently with graph execution.

The delivery queue MUST be strictly serial across the entire invocation. For a given invocation:

- No two observers receive the same event concurrently.
- No observer receives event e+1 until every observer has finished receiving event e.
- Observers receive each event in the following deterministic order:
  1. Graph-attached observers, outermost graph down to the graph that directly owns the node (within
     each graph, in registration order).
  2. Invocation-scoped observers passed to the outermost `invoke` call, in the order they were passed.

`invoke()` MUST return as soon as graph execution completes, regardless of the state of the observer
delivery queue. Observer processing may continue after `invoke()` returns.

An observer that raises an error MUST NOT interrupt the graph run, MUST NOT prevent other observers
from receiving the same event, and MUST NOT prevent any observer from receiving subsequent events.
Implementations SHOULD report observer errors through a language-idiomatic warning channel (e.g.,
Python's `warnings.warn`, TypeScript's `console.warn`).

**Drain.** The compiled graph MUST expose a `drain` operation that, when awaited, returns once all
observer events produced by prior invocations of this graph have been delivered to every registered
observer. Events produced by subgraphs during an invocation are part of that invocation and are
covered by the parent graph's drain. Callers running in short-lived processes (scripts, serverless
functions, CLIs) MUST use drain to avoid losing observer events that were dispatched but not yet
delivered.

Implementations MAY provide APIs to add or remove registered observers. Any change to the set of
registered observers during a graph run MUST NOT take effect until the next invocation — the set of
observers receiving events for an in-flight invocation is fixed at the point the invocation begins.

**Node event shape.** A node event carries the following fields:

- `node_name` — the name under which this node was registered in its immediate containing graph.
- `namespace` — an ordered sequence of node names identifying the execution path from the outermost
  graph down to this node. For a node in the outermost graph, `namespace` is `[node_name]`. For a node
  inside a subgraph, `namespace` is the chain of outer subgraph-node names followed by the inner node
  name. Nested subgraphs extend the chain. Implementations MUST NOT represent the namespace as a
  delimiter-joined string at the specification boundary — the sequence form is required so that node
  names may contain any characters without parsing ambiguity.
- `step` — a monotonically increasing non-negative integer, starting at `0`, counting node executions
  within a single invocation of the outermost graph. Subgraph-internal node executions increment the
  same counter.
- `pre_state` — the state the node received, before the reducer merge.
- `post_state` — the state after the node's partial update merged successfully via reducers. Populated
  only when the node executed to completion without raising and the merge did not raise.
- `error` — the error category identifier from §4 (e.g., `node_exception`, `reducer_error`) together
  with the raised error instance. Populated only when the node event corresponds to a failed node
  execution.

Exactly one of `post_state` or `error` MUST be populated per event.

**Event dispatch.** A node event is dispatched onto the delivery queue exactly once per node
execution:

- On successful execution, after the reducer merge has produced the post-update state and before the
  outgoing edge is evaluated.
- On failed execution (node raised, reducer raised, or state validation failed per §4), before the
  error propagates to the caller.

The engine MUST complete dispatch before proceeding to the next graph step, but it MUST NOT await
observer processing — dispatch enqueues the event; the delivery queue processes it separately per
the rules above.

`routing_error` from §4 is a consequence of evaluating an outgoing edge against a post-update state.
The node event for the preceding node has already been dispatched by the time a routing error
arises; a routing error does NOT produce its own node event.

**State immutability.** `pre_state` and `post_state` MUST present the same immutability contract as
state instances flowing through the graph (§2 Node). Attempts by an observer to mutate either MUST
fail per the implementation's state-immutability strategy (e.g., Python: frozen-instance error).

**Determinism.** Given the same initial state, same node implementations, same edge functions, and
same registered observers, the sequence of events passed to observers MUST be identical across runs.
This extends the §5 determinism guarantee to observer delivery order. Observer side effects (logging,
IO) remain out of scope for this guarantee.

### §3 Execution model (cross-reference addition)

Between step 2 (reducer merge) and step 3 (edge evaluation), the engine MUST dispatch the node event
for the just-completed node onto the observer delivery queue per §6. Dispatch completes synchronously
before step 3; observer processing happens asynchronously on the delivery queue and does not affect
node execution timing. If step 2 fails — because the node raised, a reducer raised, or state
validation failed — the engine MUST dispatch the node event (with `error` populated) before the
failure propagates to the caller.

## Conformance test impact

Add four new fixtures under `spec/graph-engine/conformance/`. Each fixture below assumes the
implementation's test harness awaits `drain` on the compiled graph after `invoke` returns and before
asserting on observer state — without drain, the observer events may not yet have been delivered.

1. **`012-observer-basic-firing`** — a linear graph with three nodes; one graph-attached observer and
   one invocation-scoped observer. Verifies:
   - Each observer is invoked exactly once per node (three events each).
   - `step` values are `0, 1, 2` in execution order.
   - `namespace` is `[node_name]` for each event.
   - `pre_state` reflects the state before the node's update merged; `post_state` reflects the state
     after.
   - Graph-attached observer receives each event before the invocation-scoped observer does.

2. **`013-observer-subgraph-namespacing-and-ordering`** — an outer graph with one subgraph-as-node;
   the subgraph has two nodes. One observer is attached to the outer graph; a second is attached to
   the subgraph. Verifies:
   - Namespaces chain as specified: outer nodes get `[outer_name]`; subgraph-internal nodes get
     `[outer_subgraph_name, inner_name]`.
   - `step` is monotonic across the subgraph boundary (e.g., `0` outer-entry, `1` inner-first,
     `2` inner-second, `3` outer-exit).
   - For outer-graph node events, only the outer-attached observer fires.
   - For subgraph-internal node events, the outer-attached observer fires first and the
     subgraph-attached observer fires second (outermost-to-innermost ordering).

3. **`014-observer-error-event`** — a graph where one node raises. Verifies:
   - The observer receives a node event for the failing node with `error` populated and `post_state`
     absent.
   - The engine then propagates the error to the caller, unchanged from its §4 contract.

4. **`015-observer-error-isolation`** — a graph with multiple nodes and two attached observers; the
   first observer raises on every event. Verifies:
   - The second observer receives every event despite the first observer's failures.
   - The graph run completes to completion.
   - The final state returned to the caller is identical to what it would have been with no
     observers.
   - The first observer's exceptions do not propagate to the caller.
   - Subsequent events are delivered to all observers despite earlier observer failures (tests
     that the delivery queue does not halt on observer error).

## Alternatives considered

**Do nothing.** Forces users either to wrap each node function in a project-local decorator (scattered
and repeated per graph) or to extend the `trace` field with richer structure (conflating execution
history with domain data, and still blind across subgraph boundaries unless the trace is projected back
per §2). Both workarounds already exist in user code and have been flagged as friction. Rejected.

**Promote the `trace` field pattern (data-side) instead.** Would make the simple case slightly easier
to set up, but cannot see inside subgraphs without the author explicitly projecting trace fields back,
cannot accept non-state-shaped data (latencies, external IDs, timing), and still requires every State
subclass to opt in. The data-side and control-side patterns are complementary; this proposal adds the
missing one rather than replacing the existing one.

**Specify middleware instead of observation.** Middleware (wrap-around with `before`/`after` hooks that
can alter state or short-circuit) is more powerful but much harder to design well: ordering semantics,
composition, error-handling contract, interaction with reducers. The charter §3.1 Principle 1 declares
the engine control-flow-agnostic; middleware would add a new control-flow mechanism. Observation is
strictly weaker, strictly safer, and solves the immediate need. A middleware proposal can come later
if observation turns out insufficient.

**Specify a pull-based streaming interface (async iterable of events).** A pull-based API is more
composable (filter, map, buffer) but has a different lifetime model and conflates the
push-vs-pull design choice with the observability one. The push-based shape specified here aligns with
how both Python and TypeScript natively express observer patterns, and a pull-based adapter can be
built on top of the callback API without further spec changes.

**Include edge-evaluation events.** Proposal 0001 §6 mentioned "edge evaluation" as a hook candidate.
Edge evaluation always happens deterministically between two node events, so edge decisions can be
reconstructed from the `post_state` of one event and the `pre_state` of the next. A dedicated event
would be useful for "why did routing go here?" diagnostics but adds event types and complicates the
shape. Defer; propose separately if observation usage surfaces a real need.

**Include state-update events separate from node events.** Proposal 0001 §6 mentioned "state updates"
as a separate hook. In this spec's execution model, state updates are a consequence of node execution
— there is no state update without a node. A separate event type would fire at the same time and
carry the same data. Fold into the node event.

**Await observers inline (vs. fire-and-forget).** An alternative design has the engine await each
observer serially between step 2 (reducer merge) and step 3 (edge evaluation). This gives observers
a guaranteed completion point before the next node runs — useful if an observer needs to finish
writing a span before the next node's span opens. Rejected because it makes observer latency part of
graph execution latency: an 80 ms-per-event exporter with three observers turns a 10-node graph's
observability overhead from 0 to 2.4 seconds of pure wait time. Predictable graph latency is a
harder property to give up than guaranteed pre-next-node observer completion, which users needing it
can approximate by calling `drain` at chosen synchronization points.

**Parallel (vs. serial) observer delivery.** Gathering observers with `asyncio.gather` (or
equivalent) so that multiple observers process the same event concurrently would improve throughput
when observer work is IO-bound. Rejected because it complicates debugging: log output from parallel
observers interleaves nondeterministically, and the composition story for multiple raising observers
requires its own design (first-error-wins, collected exceptions, etc.). Serial delivery keeps
per-run log output deterministic and error handling trivial; users with high-throughput needs can
implement fan-out inside a single observer.

**Fire two events per node (started + completed) instead of one.** Would let observers see the
pre-state before the node runs and the post-state after, as separate events. Rejected because the
single event already carries both `pre_state` and `post_state`, and the two-event model doubles the
observer-invocation overhead without information gain. The single-event-at-completion shape also
aligns naturally with the error case (one event with `error` populated instead of two events where
the second never arrives).

## Open questions

None at time of submission.
