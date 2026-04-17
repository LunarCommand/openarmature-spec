# 0001: Graph Engine Foundation

- **Status:** Accepted
- **Author:** Chris Colinsky
- **Created:** 2026-04-16
- **Accepted:** 2026-04-16
- **Targets:** spec/graph-engine/spec.md (creates)
- **Related:**
- **Supersedes:**

## Summary

Establish the foundational behavioral specification for the OpenArmature graph engine: typed state, nodes as
async functions, static and conditional edges, state reducers, subgraph composition, and the execution model
that ties them together. This is the first capability spec in the repository and the substrate every later
capability (pipeline utilities, tool system, observability) will compose against.

## Motivation

The charter (`docs/openarmature.md` §4.1) identifies the graph engine as the shared primitive across both LLM
pipelines and tool-calling agents. For that claim to hold, the engine's behavior must be specified precisely
enough that two idiomatic implementations (Python, TypeScript) produce observably identical results on the
same inputs — otherwise "shared primitive" is aspiration, not fact.

A foundation spec is also a prerequisite for almost every subsequent proposal:

- Pipeline utilities (`@step`, checkpointing, `batch_process`) compose on top of nodes and state.
- The tool system surfaces tool calls as state transitions routed by conditional edges.
- Observability wraps node execution and edge routing — it needs a defined execution model to hook into.
- Middleware, subgraph composition, and state reducers each warrant their own refinements later, but all of
  them presuppose a common core.

Ship the smallest coherent foundation first; defer the rest to follow-on proposals that can reference a stable
base.

## Detailed design

The full proposed text of `spec/graph-engine/spec.md` is reproduced below. It is written in language-agnostic
terms — Python and TypeScript map their own idioms (Pydantic vs. Zod, decorators vs. factory calls) onto the
behavioral contract described here.

---

### 1. Purpose

The graph engine defines how a workflow is structured, how state flows between steps, and how execution
progresses. It is the substrate for both deterministic LLM pipelines and LLM-driven tool-calling agents.

### 2. Concepts

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
field has exactly one reducer. The default reducer is *last-write-wins* (the new value replaces the old).
Implementations MUST provide at least: `last_write_wins`, `append` (for list-typed fields), and `merge`
(for mapping-typed fields). Users MAY register custom reducers per field.

**Subgraph.** A compiled graph used as a node inside another graph. A subgraph receives a view of the parent's
state (projected onto the subgraph's state schema) and returns a partial update merged back into the parent.
Projection and merging use the same reducer rules as ordinary nodes.

**Compiled graph.** The result of compiling a graph definition. A compiled graph is immutable and executable.
The entry node MUST be declared explicitly by the graph author — there is no implicit "first node added"
default. Compilation MUST fail with a diagnostic error if the graph has: no declared entry node, unreachable
nodes, dangling edges (references to nonexistent nodes), a node with more than one outgoing edge, or a field
with more than one declared reducer.

### 3. Execution model

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
fan-out is a separate concern addressed by pipeline utilities (future proposal), not by the base execution
model.

### 4. Error semantics

- If a node raises, execution halts and the exception propagates to the caller. The partial state at the point
  of failure MUST be recoverable (exposed on the raised error or via a documented accessor).
- If an edge function raises, behavior is identical to a node raising.
- If a reducer raises while merging a node's partial update (e.g., the `append` reducer receives a non-list
  value), the engine MUST raise a distinct `ReducerError` that names the offending field, the reducer, and
  the producing node, and that preserves the original exception as its cause (`__cause__` in Python, `cause`
  in TypeScript). Execution halts; the pre-merge state MUST be recoverable from the error.
- If a conditional edge returns a name that is not a declared node or `END`, the engine MUST raise a routing
  error before invoking any further node.
- If state validation fails at a boundary, the engine MUST raise a validation error naming the offending
  field(s).

### 5. Determinism

Given the same initial state, the same node implementations, and the same edge functions, a graph run MUST
produce the same final state and the same observed node-execution order. Nondeterminism introduced by node
implementations (wall-clock time, randomness, external I/O) is out of scope for this guarantee.

### 6. Observability hooks (informative)

The engine is expected to expose, but this proposal does not standardize, hooks for: node start, node end,
edge evaluation, and state updates. These will be specified by the observability proposal once the base
execution model is stable.

### 7. Out of scope for this proposal

Deferred to later proposals:

- **Middleware** — wrapping nodes with cross-cutting concerns (retry, timing, logging).
- **Checkpointing and resume** — pipeline utility, not a graph-engine primitive.
- **Parallel fan-out / fan-in** — batch execution of a single node over many inputs.
- **Streaming outputs** — per-node streaming of partial state updates.
- **Persistent state backends** — durable state stores beyond in-memory execution.
- **Human-in-the-loop interrupts** — pause, inspect, resume semantics.

Each of these will get its own proposal that references §3 (execution model) as its base.

---

## Conformance test impact

This proposal creates the initial `spec/graph-engine/conformance/` directory. The fixtures below are the
minimum set required to verify the behaviors specified above. Each is a YAML input + markdown description
pair, per `GOVERNANCE.md`.

Proposed initial fixtures:

1. **`001-linear-static-flow`** — three nodes, two static edges, `END`. Verifies basic execution order and
   state propagation.
2. **`002-conditional-routing`** — one node with a conditional edge selecting one of two destinations based on
   state. Verifies conditional edges are evaluated against post-update state.
3. **`003-reducer-last-write-wins`** — two nodes writing to the same scalar field. Verifies the second write
   replaces the first.
4. **`004-reducer-append`** — two nodes writing to a list-typed field with the `append` reducer. Verifies
   order and non-mutation.
5. **`005-reducer-merge`** — two nodes writing overlapping keys to a mapping-typed field with the `merge`
   reducer.
6. **`006-subgraph-composition`** — a compiled subgraph used as a node; parent state projection in, partial
   update merged back.
7. **`007-compile-errors`** — table of graph definitions that MUST fail compilation: missing entry,
   unreachable node, dangling edge, conflicting reducers.
8. **`008-routing-error`** — conditional edge returns an undeclared node name; engine raises routing error.
9. **`009-node-exception-propagation`** — a node raises; final state at failure is recoverable.
10. **`010-determinism`** — same inputs, same graph, run twice; final state and node-execution order MUST
    match byte-for-byte (for nodes whose own implementations are deterministic).

Each implementation's adapter loads these fixtures and runs them through its native test runner.

## Alternatives considered

**Do nothing.** Leaves the graph engine unspecified. Blocks every subsequent proposal that needs to reference
node, edge, or state semantics. Rejected.

**Specify only "what a graph is" and defer execution semantics.** A structural spec without execution
semantics is not testable — conformance tests need defined behavior, not defined shape. Rejected.

**Mirror LangGraph's model directly.** LangGraph's compiled-graph model is a reasonable starting point, but
its state-channel abstraction (channels with reducers) and its tight coupling to `MessagesState` for agent use
cases carry assumptions specific to tool-calling agents. OpenArmature's thesis is that pipelines are the lead
case; the spec should not bake in an agent-shaped state model at the foundation. We take the good ideas
(typed state, reducers, conditional edges, `END` sentinel) without the `MessagesState`-centric framing.

**Specify a wire protocol (JSON-RPC-style) for node invocation.** Would enable polyglot nodes within a single
graph. Too broad for the foundation, and not motivated by any of the seven referenced projects. A protocol
proposal can come later if cross-language node execution becomes a real need.

**Include middleware in the foundation.** Middleware is important, but its design (ordering, composition,
access to node context) is a non-trivial subproblem with its own tradeoffs. Including it here would delay the
foundation and produce a weaker middleware design under time pressure. A follow-on proposal is the right
shape.

## Open questions

None at time of submission. (Six questions raised during drafting were resolved before the proposal was
opened for review; resolutions are reflected in §2–§4 of the Detailed design.)
