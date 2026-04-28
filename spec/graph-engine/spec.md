# Graph Engine

Canonical behavioral specification for the OpenArmature graph engine.

- **Capability:** graph-engine
- **Introduced:** spec version 0.1.0
- **History:**
  - created by [proposal 0001](../../proposals/0001-graph-engine-foundation.md)
  - §2 Subgraph extended with explicit input/output mapping by [proposal 0002](../../proposals/0002-subgraph-explicit-mapping.md)

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
