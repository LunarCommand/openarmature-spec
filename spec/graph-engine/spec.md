# Graph Engine

Canonical behavioral specification for the OpenArmature graph engine.

- **Capability:** graph-engine
- **Introduced:** spec version 0.1.0
- **History:**
  - created by [proposal 0001](../../proposals/0001-graph-engine-foundation.md)
  - §2 Subgraph extended with explicit input/output mapping by [proposal 0002](../../proposals/0002-subgraph-explicit-mapping.md)
  - §6 Observer hooks promoted from informative to normative by [proposal 0003](../../proposals/0003-node-boundary-observer-hooks.md)

This specification is language-agnostic. Each implementation (Python, TypeScript, …) maps its own idioms
onto the behavioral contract described here. Conformance is verified by the fixtures under `conformance/`.

Normative keywords (MUST, MUST NOT, SHOULD, MAY) are used per [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).

---

## 1. Purpose

The graph engine defines how a workflow is structured, how state flows between steps, and how execution
progresses. It is the substrate for both deterministic LLM pipelines and LLM-driven tool-calling agents.

## 2. Concepts

**State.** A typed schema describing the data flowing through a graph. State is a product type (a record with
named, typed fields). Implementations MUST validate state against the schema at graph boundaries (entry, exit)
and SHOULD validate at node boundaries.

**Node.** A named unit of work. A node receives the current state and returns a partial update — a mapping
from field names to new values. Nodes MUST be asynchronous. A node MUST NOT mutate the state object it
received; it returns a new partial update which the engine merges. In languages whose typed-state
representation is effectively immutable (notably Python with Pydantic) this is directly enforceable; in
languages without value-type enforcement (notably TypeScript) implementations SHOULD defend against
accidental mutation via freezing or immutable data structures.

**Edge.** A directed connection between nodes. Edges are one of:

- **Static edge** — always routes from source node to a fixed destination.
- **Conditional edge** — a function of current state that returns the destination node name (or the sentinel
  `END`).

Each node has exactly one outgoing edge. Branching is always expressed via a conditional edge, not by
declaring multiple static edges from the same source.

**END.** An engine-provided sentinel value used as a routing target to halt execution. `END` is a distinct
engine constant, not a reserved node name, so a user node may happen to be named `"END"` without collision.

**Reducer.** A function that merges a node's partial update into the prior state for a given field. Each state
field has exactly one reducer. The default reducer is _last-write-wins_ (the new value replaces the old).
Implementations MUST provide at least: `last_write_wins`, `append` (for list-typed fields), and `merge`
(for mapping-typed fields). Users MAY register custom reducers per field.

**Subgraph.** A compiled graph used as a node inside another graph. A subgraph executes against its own state
schema and produces a partial update that is merged into the parent's state. The merge uses the same reducer
rules as ordinary nodes — parent reducers, applied to parent fields.

By default, no projection in occurs: the subgraph runs from the initial state defined by its own schema's
field defaults, independent of the parent's current state.

Projection out defaults to **field-name matching**: when the subgraph completes, the values of any subgraph
fields whose names match parent fields are merged into those parent fields via the parent's reducers.
Subgraph fields with no matching parent field are discarded.

**Explicit input/output mapping.** A subgraph-as-node MAY declare an `inputs` mapping, an `outputs` mapping,
or both:

- `inputs`: a mapping from subgraph field name → parent field name. For each entry, the parent field's
  current value is copied to the subgraph's corresponding field at entry. Subgraph fields not named in
  `inputs` receive their schema-declared default — they are NOT filled by field-name matching as a
  fallback.
- `outputs`: a mapping from parent field name → subgraph field name. For each entry, the subgraph's final
  value for the named subgraph field is merged into the corresponding parent field via the parent's
  reducer for that field. Subgraph fields not named in `outputs` are discarded — they do NOT fall through
  to field-name matching.

The two directions are independent: a subgraph-as-node MAY declare `inputs` only, `outputs` only, both, or
neither.

- When `inputs` is absent, the default above applies: no projection in. The subgraph runs from its own
  schema defaults.
- When `inputs` is present, named parent fields are copied to their mapped subgraph fields at entry; all
  other subgraph fields receive their schema-declared defaults.
- When `outputs` is absent, the default above applies: subgraph fields whose names match parent fields are
  merged back via the parent's reducers; non-matching subgraph fields are discarded.
- When `outputs` is present, it **replaces** field-name matching for projection-out: only the
  parent/subgraph field pairs named in `outputs` are merged, via the parent's reducer for the named parent
  field. All other subgraph fields are discarded.

This asymmetry — `inputs` additive, `outputs` replacement — is intentional. It reflects the asymmetry in
the defaults themselves: projection-in is off by default (so `inputs` turns it on for listed fields), while
projection-out is on by default via field-name matching (so `outputs` replaces it to avoid ambiguous mixed
rules).

Compilation MUST fail with category `mapping_references_undeclared_field` if an `inputs` mapping names a
parent field that is not declared in the parent's state schema, or a subgraph field that is not declared in
the subgraph's state schema. The same rule applies symmetrically to `outputs`. Implementations SHOULD
validate at compile time that the types of mapped parent/subgraph field pairs are compatible (per the
language's type system's notion of compatibility); this is SHOULD rather than MUST because type-system
expressiveness varies across languages.

**Compiled graph.** The result of compiling a graph definition. A compiled graph is immutable and executable.
The entry node MUST be declared explicitly by the graph author — there is no implicit "first node added"
default. Compilation MUST fail with a diagnostic error if the graph has: no declared entry node, unreachable
nodes, dangling edges (references to nonexistent nodes), a node with more than one outgoing edge, or a field
with more than one declared reducer.

When reporting a compile-time error, implementations MUST expose one of the following canonical category
identifiers (as an error class, error code, or tagged discriminant, per the language's idiom):

- `no_declared_entry` — no entry node was declared.
- `unreachable_node` — a declared node has no path from the entry.
- `dangling_edge` — an edge references a node name that is not declared.
- `multiple_outgoing_edges` — a node has more than one outgoing edge.
- `conflicting_reducers` — a state field has more than one declared reducer.
- `mapping_references_undeclared_field` — a subgraph-as-node `inputs` or `outputs` mapping names a field
  not declared in the relevant state schema.

## 3. Execution model

1. Execution begins at the designated **entry** node with the initial state supplied by the caller.
2. The current node's async function is invoked with the current state. Its returned partial update is merged
   into state using each field's reducer.
3. Between the merge in step 2 and the edge evaluation in step 4, the engine MUST dispatch the node event
   for the just-completed node onto the observer delivery queue per §6. Dispatch completes synchronously
   before step 4; observer processing happens asynchronously on the delivery queue and does not affect
   node execution timing. If step 2 fails — because the node raised, a reducer raised, or state validation
   failed — the engine MUST dispatch the node event (with `error` populated) before the failure
   propagates to the caller.
4. The engine then evaluates the outgoing edge from the current node:

- If static: route to the fixed destination.
- If conditional: invoke the edge function with the **post-update** state — i.e., the state reflecting the
  partial update merged in step 2. The returned value is the destination node name or the `END` sentinel.

5. If the destination is `END`, execution halts and the final state is returned.
6. Otherwise, repeat from step 2 with the destination node.

Execution is single-threaded per invocation: one node is active at a time within a given graph run. Parallel
fan-out is a separate concern addressed by pipeline utilities (future capability), not by the base execution
model.

## 4. Error semantics

- If a node raises, execution halts and the exception propagates to the caller. The partial state at the point
  of failure MUST be recoverable (exposed on the raised error or via a documented accessor).
- If an edge function raises, behavior is identical to a node raising.
- If a reducer raises while merging a node's partial update (e.g., the `append` reducer receives a non-list
  value), the engine MUST raise a distinct `ReducerError` that names the offending field, the reducer, and
  the producing node, and that preserves the original exception as its cause (`__cause__` in Python, `cause`
  in TypeScript). Execution halts; the pre-merge state MUST be recoverable from the error.
- If a conditional edge returns a name that is not a declared node or `END`, the engine MUST raise a routing
  error before invoking any further node. The state at the point of failure MUST be recoverable from the
  error, matching the node-exception contract.
- If state validation fails at a boundary, the engine MUST raise a validation error naming the offending
  field(s).

When reporting a runtime error, implementations MUST expose one of the following canonical category
identifiers (as an error class, error code, or tagged discriminant, per the language's idiom):

- `node_exception` — a node raised. The user's exception propagates; the engine attaches recoverable state.
- `edge_exception` — an edge function raised. Behaves identically to `node_exception`.
- `reducer_error` — a reducer raised while merging. Surface class: `ReducerError` (see earlier bullet).
- `routing_error` — a conditional edge returned a destination that is neither a declared node nor `END`.
- `state_validation_error` — state failed schema validation at a graph boundary.

## 5. Determinism

Given the same initial state, the same node implementations, and the same edge functions, a graph run MUST
produce the same final state and the same observed node-execution order. Nondeterminism introduced by node
implementations (wall-clock time, randomness, external I/O) is out of scope for this guarantee.

## 6. Observer hooks

The compiled graph MUST expose a way to register one or more **observers**. An observer is a function or
callable that receives a **node event** and returns nothing of interest to the engine. Observers inspect
execution as it happens; they MUST NOT alter state, routing, or any other aspect of the graph run.

An implementation MUST support at least two registration modes:

- **Graph-attached.** Observers registered on a compiled graph fire on every invocation of that graph
  until removed.
- **Invocation-scoped.** Observers passed to a single invocation fire only for that invocation.

An implementation MAY provide additional registration modes; these two are the minimum.

Observers attached to a compiled graph fire whenever that graph runs — whether invoked directly by a
caller or as a subgraph inside a parent. A subgraph's attached observers therefore receive events for the
subgraph's internal nodes during a parent run, in addition to any observers attached to or passed to the
parent.

Observers MUST be asynchronous — the delivery queue awaits each observer to coordinate its completion. In
Python this means `async def` observers; in TypeScript, functions returning `Promise<void>`. An
implementation MAY accept synchronous observers by wrapping them internally, but this specification models
observers as async to keep delivery semantics well-defined.

**Event delivery.** Observer events are delivered asynchronously with respect to graph execution. The
graph's execution loop MUST NOT await observer processing; observer latency MUST NOT affect node execution
timing. Each invocation of the outermost graph has an observer delivery queue that runs concurrently with
graph execution.

The delivery queue MUST be strictly serial across the entire invocation. For a given invocation:

- No two observers receive the same event concurrently.
- No observer receives event e+1 until every observer has finished receiving event e.
- Observers receive each event in the following deterministic order:
  1. Graph-attached observers, outermost graph down to the graph that directly owns the node (within each
     graph, in registration order).
  2. Invocation-scoped observers passed to the outermost `invoke` call, in the order they were passed.

`invoke()` MUST return as soon as graph execution completes, regardless of the state of the observer
delivery queue. Observer processing may continue after `invoke()` returns.

An observer that raises an error MUST NOT interrupt the graph run, MUST NOT prevent other observers from
receiving the same event, and MUST NOT prevent any observer from receiving subsequent events.
Implementations SHOULD report observer errors through a language-idiomatic warning channel (e.g.,
Python's `warnings.warn`, TypeScript's `console.warn`).

**Drain.** The compiled graph MUST expose a `drain` operation that, when awaited, returns once all
observer events produced by prior invocations of this graph have been delivered to every registered
observer. Events produced by subgraphs during an invocation are part of that invocation and are covered
by the parent graph's drain. Callers running in short-lived processes (scripts, serverless functions,
CLIs) MUST use drain to avoid losing observer events that were dispatched but not yet delivered.

Implementations MAY provide APIs to add or remove registered observers. Any change to the set of
registered observers during a graph run MUST NOT take effect until the next invocation — the set of
observers receiving events for an in-flight invocation is fixed at the point the invocation begins.

**Node event shape.** A node event carries the following fields:

- `node_name` — the name under which this node was registered in its immediate containing graph.
- `namespace` — an ordered sequence of node names identifying the execution path from the outermost graph
  down to this node. For a node in the outermost graph, `namespace` is `[node_name]`. For a node inside a
  subgraph, `namespace` is the chain of outer subgraph-node names followed by the inner node name. Nested
  subgraphs extend the chain. Implementations MUST NOT represent the namespace as a delimiter-joined
  string at the specification boundary — the sequence form is required so that node names may contain any
  characters without parsing ambiguity.
- `step` — a monotonically increasing non-negative integer, starting at `0`, counting node executions
  within a single invocation of the outermost graph. Subgraph-internal node executions increment the same
  counter.
- `pre_state` — the state the node received, before the reducer merge. For a node in the outermost
  graph, this is the outermost state. For a node inside a subgraph, this is the subgraph's state — the
  state the inner node actually received. State shape therefore varies with `namespace`.
- `post_state` — the state after the node's partial update merged successfully via reducers. Populated
  only when the node executed to completion without raising and the merge did not raise. Same
  shape-varies-with-namespace rule as `pre_state`.
- `error` — the error category identifier from §4 (e.g., `node_exception`, `reducer_error`) together with
  the raised error instance. Populated only when the node event corresponds to a failed node execution.
- `parent_states` — an ordered sequence of state snapshots, one per containing graph, outermost first.
  For a node in the outermost graph, `parent_states` is empty. For a node inside a subgraph,
  `parent_states[0]` is the outermost graph's state, `parent_states[1]` is the next-inner containing
  graph's state, and so on; the last entry is the immediate parent's state. The invariant
  `len(parent_states) == len(namespace) - 1` MUST hold.

Exactly one of `post_state` or `error` MUST be populated per event.

**Parent-state snapshot semantics.** Each entry of `parent_states` is the corresponding containing graph's
state **at the moment that graph entered the subgraph-as-node leading down to this event**. The parent is
not stepping while the subgraph runs, so all node events emitted from a single subgraph run share the
same `parent_states` snapshots. The shape of each entry is the corresponding graph's own state schema —
it is NOT projected, mapped, or otherwise transformed.

**Event dispatch.** A node event is dispatched onto the delivery queue exactly once per node execution:

- On successful execution, after the reducer merge has produced the post-update state and before the
  outgoing edge is evaluated.
- On failed execution (node raised, reducer raised, or state validation failed per §4), before the error
  propagates to the caller.

The engine MUST complete dispatch before proceeding to the next graph step, but it MUST NOT await
observer processing — dispatch enqueues the event; the delivery queue processes it separately per the
rules above.

`routing_error` from §4 is a consequence of evaluating an outgoing edge against a post-update state. The
node event for the preceding node has already been dispatched by the time a routing error arises; a
routing error does NOT produce its own node event.

**State immutability.** `pre_state`, `post_state`, and every entry of `parent_states` MUST present the
same immutability contract as state instances flowing through the graph (§2 Node). Attempts by an
observer to mutate any of them MUST fail per the implementation's state-immutability strategy (e.g.,
Python: frozen-instance error).

**Determinism.** Given the same initial state, same node implementations, same edge functions, and same
registered observers, the sequence of events passed to observers MUST be identical across runs. This
extends the §5 determinism guarantee to observer delivery order. Observer side effects (logging, IO)
remain out of scope for this guarantee.

## 7. Out of scope

Not covered by this specification; deferred to follow-on capabilities or proposals:

- **Middleware** — wrapping nodes with cross-cutting concerns (retry, timing, logging).
- **Checkpointing and resume** — pipeline utility, not a graph-engine primitive.
- **Parallel fan-out / fan-in** — batch execution of a single node over many inputs.
- **Streaming outputs** — per-node streaming of partial state updates.
- **Persistent state backends** — durable state stores beyond in-memory execution.
- **Human-in-the-loop interrupts** — pause, inspect, resume semantics.
