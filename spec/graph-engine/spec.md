# Graph Engine

Canonical behavioral specification for the OpenArmature graph engine.

- **Capability:** graph-engine
- **Introduced:** spec version 0.1.0
- **History:** created by [proposal 0001](../../proposals/0001-graph-engine-foundation.md)

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
Subgraph fields with no matching parent field are discarded. Alternative projection strategies (e.g.,
explicit input/output mapping that copies named parent fields into the subgraph at entry) are out of scope
for this specification and will be addressed by follow-on proposals.

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

## 3. Execution model

1. Execution begins at the designated **entry** node with the initial state supplied by the caller.
2. The current node's async function is invoked with the current state. Its returned partial update is merged
   into state using each field's reducer.
3. The engine then evaluates the outgoing edge from the current node:

- If static: route to the fixed destination.
- If conditional: invoke the edge function with the **post-update** state — i.e., the state reflecting the
  partial update merged in step 2. The returned value is the destination node name or the `END` sentinel.

4. If the destination is `END`, execution halts and the final state is returned.
5. Otherwise, repeat from step 2 with the destination node.

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

## 6. Observability hooks (informative)

The engine is expected to expose, but this specification does not standardize, hooks for: node start, node
end, edge evaluation, and state updates. These will be specified alongside the observability capability once
that spec lands.

## 7. Out of scope

Not covered by this specification; deferred to follow-on capabilities or proposals:

- **Middleware** — wrapping nodes with cross-cutting concerns (retry, timing, logging).
- **Checkpointing and resume** — pipeline utility, not a graph-engine primitive.
- **Parallel fan-out / fan-in** — batch execution of a single node over many inputs.
- **Streaming outputs** — per-node streaming of partial state updates.
- **Persistent state backends** — durable state stores beyond in-memory execution.
- **Human-in-the-loop interrupts** — pause, inspect, resume semantics.
