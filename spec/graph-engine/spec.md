# Graph Engine

Canonical behavioral specification for the OpenArmature graph engine.

- **Capability:** graph-engine
- **Introduced:** spec version 0.1.0
- **History:**
  - created by [proposal 0001](../../proposals/0001-graph-engine-foundation.md)
  - §2 Subgraph extended with explicit input/output mapping by [proposal 0002](../../proposals/0002-subgraph-explicit-mapping.md)
  - §6 Observer hooks promoted from informative to normative by [proposal 0003](../../proposals/0003-node-boundary-observer-hooks.md)
  - §6 Observer hooks gained `attempt_index` field and middleware-dispatched events by [proposal 0004](../../proposals/0004-pipeline-utilities-middleware.md)
  - §3 Execution model carved out a fan-out concurrency exception; §6 Observer hooks replaced single-event-per-attempt with started/completed pairs, added per-observer phase subscription, added `fan_out_index` field, and removed the "Middleware-dispatched events" subsection by [proposal 0005](../../proposals/0005-pipeline-utilities-parallel-fan-out.md)
  - §3 Execution model concurrency exception extended to also cover parallel-branches; §6 Observer hooks gained `branch_name` field and updated event-source uniqueness invariant to include it by [proposal 0011](../../proposals/0011-pipeline-utilities-parallel-branches.md)
  - §6 Observer hooks `drain` operation gained an optional caller-supplied `timeout` parameter and now MUST return a summary (`undelivered_count`, `timeout_reached`, with implementations permitted to add richer detail); under timeout, workers MUST be cancelled and graph state MUST remain usable for subsequent invocations by [proposal 0010](../../proposals/0010-drain-timeout.md)
  - §6 Drain gained two clarifications of implicit rules: the snapshot semantic for "prior invocations" (drain covers workers active at call time; invocations started during the drain are NOT covered), and the MUST-reject rule for negative / NaN timeout inputs (with the error surface per-language idiomatic) by [proposal 0030](../../proposals/0030-drain-snapshot-and-timeout-validation.md)
  - §3 *Execution model* gained a clarifying paragraph noting that `invoke()` accepts an optional caller-supplied metadata mapping (per observability §3.4) alongside the existing `correlation_id` argument and per-language invocation surface by [proposal 0034](../../proposals/0034-caller-supplied-invocation-metadata.md)

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
Implementations MUST provide at least: `last_write_wins`, `append` (for list-typed fields), `merge`
(for mapping-typed fields), `concat_flatten` (for list-typed fields whose updates are lists of lists —
e.g., fan-out target fields collecting list-emitting per-instance values), and `merge_all` (for
mapping-typed fields whose updates are lists of mappings — e.g., fan-out target fields collecting
dict-emitting per-instance values). Users MAY register custom reducers per field.

**`concat_flatten` semantics.** `concat_flatten(prior, update)` returns the concatenation of `prior` with the
one-level flattening of `update`. Both `prior` and `update` MUST be lists, and every element of `update` MUST
itself be a list. Violations raise `ReducerError` per §4 (the engine MUST surface the offending field, the
reducer name, and a root-cause naming the non-list value). Empty `update` is a no-op (returns `prior`
unchanged). Empty sub-lists inside `update` contribute zero elements (the one-to-many fan-out case where an
instance legitimately produces zero records). Implementations MUST NOT auto-detect whether `update` is a list
of lists vs. a flat list — `concat_flatten` is strictly the two-level reducer; callers with mixed-shape
requirements MUST register a custom reducer rather than rely on shape-dependent behavior.

**`merge_all` semantics.** `merge_all(prior, update)` folds the sequence of mappings in `update` into `prior`,
applying the same shallow merge semantics as `merge` (later writes win on key conflict; non-conflicting keys
from `prior` are preserved). For `update = [d_1, d_2, ..., d_n]`, the result is equivalent to applying `merge`
N times sequentially: `merge(merge(...merge(merge(prior, d_1), d_2)...), d_n)`, so within `update`
last-write-wins applies across all N dicts (e.g., if `d_2` and `d_n` both set key `k`, `d_n`'s value wins).
`prior` MUST be a mapping, `update` MUST be a list, and every element of `update` MUST itself be a mapping.
Violations raise `ReducerError` per §4. Empty `update` is a no-op (returns `prior` unchanged). Empty mappings
inside `update` contribute zero keys. Implementations MUST NOT auto-detect whether `update` is a list of
mappings vs. a single mapping — `merge_all` is strictly the list-of-mappings reducer; callers needing both
behaviors on the same field MUST register a custom reducer rather than rely on shape-dependent behavior.

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
3. After the merge in step 2 AND the edge evaluation in step 4 both complete, the engine MUST dispatch
   the node event for the just-completed node onto the observer delivery queue per §6. Dispatch
   completes synchronously before the next step 2 begins; observer processing happens asynchronously
   on the delivery queue and does not affect node execution timing. The dispatched event captures the
   node's complete transition: its body's execution, the reducer merge, and the resolution of its
   outgoing edge. If any of those steps fail — because the node raised, a reducer raised, state
   validation failed, the edge function raised (`edge_exception`), or no matching edge was returned
   (`routing_error`) — the engine MUST dispatch the node event (with `error` populated) before the
   failure propagates to the caller.
4. The engine then evaluates the outgoing edge from the current node:

- If static: route to the fixed destination.
- If conditional: invoke the edge function with the **post-update** state — i.e., the state reflecting the
  partial update merged in step 2. The returned value is the destination node name or the `END` sentinel.

5. If the destination is `END`, execution halts and the final state is returned.
6. Otherwise, repeat from step 2 with the destination node.

Execution is single-threaded per invocation **except inside a fan-out node** (pipeline-utilities §9) **or
inside a parallel-branches node** (pipeline-utilities §11): one node is active at a time within a given
graph run, with the bounded exceptions that a fan-out node may execute multiple subgraph instances
concurrently and a parallel-branches node may execute multiple heterogeneous compiled subgraphs
concurrently. After a fan-out or parallel-branches node completes, single-threaded execution resumes for
the rest of the parent run.

**Invocation entry surface.** The `invoke()` operation accepts the initial state, an optional
caller-supplied `correlation_id` (per observability §3.1), an optional caller-supplied
`invocation_id` (per observability §5.1 — used verbatim when supplied, framework-minted as a
UUIDv4 when absent; on a resume call the framework always mints a fresh id and ignores any
caller-supplied `invocation_id`), and an optional caller-supplied metadata mapping (per
observability §3.4). The metadata mapping carries arbitrary OTel-attribute-compatible key/value
entries that propagate to every observability backend the implementation emits to. The exact
mechanism by which callers supply these arguments at invoke time is per-language idiomatic (a
keyword argument; a field on an invocation-config record; equivalent); the graph-engine spec
does not prescribe the mechanism. The contracts for how these arguments are validated and
propagated live in the observability spec (§3.1 for `correlation_id`, §5.1 for `invocation_id`,
§3.4 for caller-supplied metadata).

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

Both registration modes accept an optional `phases` parameter — a set of phase strings the observer
subscribes to. See "Per-observer phase subscription" below.

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
observer, OR once an optional caller-supplied timeout elapses, whichever happens first. Events
produced by subgraphs during an invocation are part of that invocation and are covered by the parent
graph's drain. Callers running in short-lived processes (scripts, serverless functions, CLIs) MUST
use drain to avoid losing observer events that were dispatched but not yet delivered.

The set of invocations covered by a `drain` call is the set whose worker(s) were active at the time
`drain` is invoked. Invocations started after `drain` is called are NOT covered by that drain;
callers needing delivery guarantees for a later invocation MUST call `drain` again after the later
invocation begins. The snapshot semantic composes cleanly with the optional `timeout`: the deadline
applies to a known finite set of workers captured at call time, rather than an open-ended set that
new invocations could extend past the deadline.

The `drain` operation MUST accept an optional **timeout** parameter (interpreted as a non-negative
duration in seconds, mapped to the host language's idiomatic wait-bound type — for example, Python's
`float` seconds). If the timeout is omitted or `None`, drain waits indefinitely (the existing v0.3.0
behavior). If a timeout is supplied:

- drain MUST return no later than `timeout` seconds after the call begins;
- any observer events still queued or in-flight when the timeout is reached are considered
  **undelivered** for the purposes of this invocation's drain;
- workers MUST be cancelled or otherwise terminated such that the compiled graph remains usable for
  subsequent invocations — partial delivery state from one drain MUST NOT leak into the next
  invocation;
- observers SHOULD be written to be cancellation-safe (idempotent writes, try/finally cleanup) so
  that interruption by drain timeout does not leave partial side effects in an inconsistent state;
- implementations MUST reject negative or `NaN` timeout inputs by raising an API-boundary error
  before any drain work begins. The error surface is per-language idiomatic (e.g., a Python
  `ValueError`, a TypeScript `RangeError`, a Go error return value); the spec mandates the
  rejection, not the error type. Non-numeric input is rejected per the language's type-error idiom
  (e.g., a Python `TypeError` from the underlying comparison or validation);

drain MUST return a summary of the drain's outcome, in a form appropriate to the host language. The
summary MUST include at least: the count of undelivered events, and a boolean or equivalent flag
indicating whether the timeout was reached. Implementations MAY provide richer detail (per-observer
counts, sampled event metadata). When called without a timeout, drain MUST still return a summary;
in that case the undelivered count is `0` and the timeout-reached flag is `false`. Callers receive
a consistent shape regardless of whether they supplied a timeout.

Implementations SHOULD document drain's worst-case duration in the presence of slow observers and
SHOULD recommend setting a timeout in short-lived process contexts (CLIs, scripts, serverless
functions).

Implementations MAY provide APIs to add or remove registered observers. Any change to the set of
registered observers during a graph run MUST NOT take effect until the next invocation — the set of
observers receiving events for an in-flight invocation is fixed at the point the invocation begins.

**Node event shape.** A *node* event — the `started` / `completed` pair below, as distinct from the
framework-emitted augmentation events described under *Framework-emitted augmentation events* later in
this section, which carry no `phase` — carries the following fields:

- `phase` — required, one of `"started"` or `"completed"`. `started` events are dispatched before the
  node executes (after middleware pre-phases; right before the wrapped function call). `completed`
  events are dispatched after the node returns or raises and the reducer merge runs (or after the
  failure is captured, on failure). Each node attempt produces exactly one `started` and exactly one
  `completed` event in that order.
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
- `attempt_index` — non-negative integer, default `0`. The 0-based index of this attempt among any
  retries of the same node within a single invocation. `attempt_index` increments per attempt
  (`0` for the first, `1` for the second, and so on through the final attempt) for nodes whose
  execution is wrapped by retry middleware that re-attempts execution — including both **direct**
  wrapping (the node's own per-node middleware chain, per pipeline-utilities §6.1) and **transitive**
  wrapping (middleware on a containing subgraph that the node is part of, per pipeline-utilities
  §9.7 instance middleware and §11.7 branch middleware). When a wrapping retry re-invokes a
  containing subgraph, the inner nodes' events MUST emit the wrapping retry's current attempt
  index — the retry counter propagates through the wrapping chain to event emissions from anything
  re-executed as part of the retried unit. For nodes with NO re-attempting middleware anywhere in
  the wrapping chain, `attempt_index` MUST be `0`. When multiple retry middlewares apply to the
  same node — whether by stacking on the per-node middleware chain or by composing direct with
  transitive wrapping — `attempt_index` reflects the **innermost** retry's counter (the retry
  closest to the node in the wrapping chain). Outer retries' attempt counters do NOT propagate
  through inner retry middleware to events below it; the outer counter is internal to the outer
  retry's runtime state and is not surfaced on §6 events from the shadowed node. (Observability
  layers MAY expose outer-retry context via span attributes on synthesized spans for containing
  subgraph / branch / fan-out instance constructs per observability §4's mapping; that is an
  observability-layer concern outside the §6 event shape.) This matches the natural semantics
  of ContextVar-style propagation (innermost set shadows outer); implementations using
  explicit-threading mechanisms SHOULD preserve the same precedence. `attempt_index` is part of
  the **event-source identification tuple** alongside `namespace`, `branch_name`, `fan_out_index`,
  and `phase` — see the `branch_name` and `fan_out_index` entries below for how this tuple
  distinguishes events from the same node name appearing in different fan-out instances or
  branches. Within a single source, `step` orders individual events emitted across multiple
  invocations (e.g., agent-loop iterations of the same node). The §6 invariant
  `len(parent_states) == len(namespace) - 1` is unaffected; `attempt_index` is independent of the
  namespace chain and parent-state list.
- `fan_out_index` — optional non-negative integer. Populated only for events from nodes that execute
  inside a fan-out instance (pipeline-utilities §9). The 0-based index of this fan-out instance among
  its siblings (in `items_field` mode, matching the position of the corresponding item; in `count`
  mode, `0..count-1`). When the same node name appears in multiple fan-out instances, the
  combination of `namespace`, `branch_name`, `fan_out_index`, `attempt_index`, and `phase` uniquely
  identifies the event source. Absent for events from nodes that are not inside any fan-out instance.
- `branch_name` — optional non-empty string. Populated only for events from nodes that execute inside
  a parallel-branches branch (pipeline-utilities §11). Carries the branch's name as declared in the
  parallel-branches node's `branches` mapping. When the same node name appears in multiple branches'
  subgraphs, the combination of `namespace`, `branch_name`, `fan_out_index`, `attempt_index`, and
  `phase` uniquely identifies the event source. `branch_name` and `fan_out_index` are independent and
  MAY both be present simultaneously when a fan-out node executes inside a parallel-branches branch
  (or a parallel-branches node executes inside a fan-out instance). Absent for events from nodes that
  are not inside any parallel-branches branch. In the uniqueness tuple, an absent field participates
  as a distinct slot: `branch_name = absent` and `branch_name = "alpha"` identify different events;
  the same applies to `fan_out_index`. This matches the convention `fan_out_index` followed
  pre-amendment.
- `fan_out_config` — optional structured value, populated on EVERY `started` and `completed`
  event for a fan-out node (i.e., events whose `node_name` resolves to a fan-out node per
  pipeline-utilities §9), including retried attempts of the fan-out node itself
  (`attempt_index > 0`). Carries the resolved values for the observability §5.4 fan-out
  attributes. Absent (null / None / equivalent) on all events from non-fan-out nodes —
  inner-node events from inside a fan-out instance (those carry `fan_out_index` instead),
  subgraph wrapper events, function-node events whether retried or not, and so on. The value
  carries four fields:
  - `item_count` — non-negative integer. The resolved instance count for this fan-out invocation.
    Equal to `len(items_field_value)` in `items_field` mode and to the resolved `count` in `count`
    mode (per pipeline-utilities §9). Available at fan-out entry, so populated on both `started`
    and `completed` events of the fan-out node.
  - `concurrency` — positive integer or null (unbounded). The resolved concurrency bound for
    this fan-out invocation, after evaluating the int-or-callable from pipeline-utilities §9.
    Matches §9.2's resolved type — zero or negative values are invalid at the configuration
    boundary (raised as `fan_out_invalid_concurrency` per §9.2) and therefore never appear here;
    null indicates unbounded. The `0` sentinel in observability §5.4's
    `openarmature.fan_out.concurrency` attribute is an OTel-attribute-mapping pragmatism (OTel
    primitives can't carry null) and does NOT appear on this canonical field. Available at
    fan-out entry, so populated on both `started` and `completed` events.
  - `error_policy` — string, exactly one of `"fail_fast"` or `"collect"` (per pipeline-utilities
    §9, `error_policy`). Populated on both `started` and `completed` events.
  - `parent_node_name` — string. The fan-out node's own name in the parent graph (i.e., equal to
    `node_name` on this event). Surfaced explicitly so observers and downstream consumers do not
    need to rederive it from `namespace`. Populated on both `started` and `completed` events.

  Implementations MUST present all four keys of `fan_out_config` whenever the field itself is
  populated on a fan-out node event — `item_count`, `concurrency`, `error_policy`, and
  `parent_node_name`. Keys are never individually omitted on the basis of an implementation's
  representation; observers can rely on key presence. Of the four, only `concurrency` is
  nullable (null indicates unbounded per pipeline-utilities §9.2); `item_count`, `error_policy`,
  and `parent_node_name` are always non-null when `fan_out_config` is populated.

  `fan_out_config` MUST be populated on a fan-out node's `completed` event regardless of whether
  the event carries `post_state` or `error` — i.e., even when the fan-out itself raised
  (`fan_out_empty`, `fan_out_invalid_count`, `fan_out_field_not_list`, etc.) at runtime after
  config resolution succeeded, the resolved configuration that was visible at fan-out entry MUST
  appear on the completed event with all four keys populated.

  Behavior in the rare case where engine configuration resolution itself fails (e.g., a
  `concurrency` or `count` callable raises) is implementation-defined for v0.10.0 — whether the
  engine dispatches a fan-out node event pair at all in that case, and if so what shape
  `fan_out_config` takes for partially-resolved configurations, is left to a future proposal.
  Conformance does not depend on this corner: existing fixtures exercise the success path and
  the post-config-resolution runtime-failure paths only.

`pre_state` is populated on both `started` and `completed` events (it is the state the node received,
identical across the pair). `post_state` and `error` are populated only on `completed` events;
exactly one of them MUST be populated on a `completed` event. `started` events MUST have both
`post_state` and `error` absent.

**Parent-state snapshot semantics.** Each entry of `parent_states` is the corresponding containing graph's
state **at the moment that graph entered the subgraph-as-node leading down to this event**. The parent is
not stepping while the subgraph runs, so all node events emitted from a single subgraph run share the
same `parent_states` snapshots. The shape of each entry is the corresponding graph's own state schema —
it is NOT projected, mapped, or otherwise transformed.

**Event dispatch.** Each node attempt produces a started/completed event pair. The engine dispatches
the `started` event before invoking the wrapped node function (after all middleware pre-phases run
per pipeline-utilities §2); the engine dispatches the `completed` event after the reducer merge
succeeds (with `post_state` populated) or after the node, reducer, or state validation fails (with
`error` populated per §4). Both dispatches happen synchronously before the engine proceeds to the
next graph step; neither awaits observer processing.

For a given attempt, the `started` event is delivered to subscribed observers strictly before the
`completed` event for that same attempt.

For nodes wrapped by middleware that re-attempts (e.g., pipeline-utilities §6.1 retry), each attempt
invokes the wrapped node function, which triggers a fresh started/completed pair from the engine. A
3-attempt retry produces 6 events: pairs at `attempt_index` 0, 1, 2 in order. The engine dispatches
all events; middleware does NOT dispatch directly.

`routing_error` and `edge_exception` from §4 are consequences of evaluating an outgoing edge against
a post-update state. Per §3 step 3, the `completed` event fires after edge evaluation completes — so
an edge-resolution failure populates the `error` field of the preceding node's `completed` event.
Edge-resolution failures do NOT produce a separate event pair; they share the preceding node's pair,
and the observer applies its standard §4.2 status-mapping path to surface the error category and
exception details on that node's span (per the observability spec mapping).

**Per-observer phase subscription.** Observer registration (graph-attached or invocation-scoped)
accepts an optional `phases` parameter — a set of phase strings the observer subscribes to.
Accepted values:

- `{"started", "completed"}` — both phases. **Default if `phases` is not specified.**
- `{"completed"}` — only `completed` events. Useful for metrics aggregators, completion-only
  loggers, retry-classification observers.
- `{"started"}` — only `started` events. Useful for stuck-node detectors and "node entered"
  alerting.

Empty phase sets are not permitted; implementations SHOULD raise at registration time.

When delivering events, the engine MUST check the receiving observer's `phases` set before dispatch
to that observer; it MUST NOT deliver an event whose phase is not in the subscribed set. This rule
governs node-boundary events, which carry a `phase`; framework-emitted augmentation events (see
*Framework-emitted augmentation events* below) carry no `phase` and are not subject to the `phases`
filter — they are delivered to every registered observer, which ignores them if it does not handle
augmentation events. Observers
with different phase subscriptions on the same graph or invocation are permitted and common — for
example, an OpenTelemetry observer subscribes to both for span boundaries while a metrics observer
subscribes to `completed` only.

The phase filter applies at delivery, not dispatch — the engine still produces both events for every
attempt; observers that don't subscribe simply don't receive them. This keeps the delivery-queue
invariants and §5 determinism intact regardless of observer mix.

**State immutability.** `pre_state`, `post_state`, and every entry of `parent_states` MUST present the
same immutability contract as state instances flowing through the graph (§2 Node). Attempts by an
observer to mutate any of them MUST fail per the implementation's state-immutability strategy (e.g.,
Python: frozen-instance error).

**Determinism.** Given the same initial state, same node implementations, same edge functions, and same
registered observers, the sequence of events passed to observers MUST be identical across runs. This
extends the §5 determinism guarantee to observer delivery order. Observer side effects (logging, IO)
remain out of scope for this guarantee.

**Framework-emitted augmentation events.** Beyond node-boundary `started` / `completed` pairs, the
observer delivery queue MAY also carry framework-emitted observability events that are not node-boundary
events — specifically the metadata-augmentation event defined in observability §3.4 / §6, emitted when
`set_invocation_metadata` adds entries mid-invocation. An augmentation event is a **distinct event
kind**, delivered to observers via a per-language-idiomatic representation (a discriminated union
carrying an explicit `kind` discriminator, a separate observer callback, equivalent). It carries no
`phase` — the `phase` field and its `started` / `completed` enumeration (per *Node event shape* above)
are properties of node-boundary events only — and none of the node-only fields (`pre_state`,
`post_state`, `error`); it carries the added metadata entries plus the lineage-identity fields it reuses
from the node event (`namespace`, `attempt_index`, `fan_out_index`, `branch_name`). Augmentation events
are delivered in the same strict-serial order as node-boundary events, at the point the augmentation
occurs. Because the `phases` subscription filter governs node-boundary phases, augmentation events are
not subject to it: they are delivered to every registered observer, which ignores them if it does not
handle augmentation events. graph-engine does not define the augmentation event's full semantics beyond
this representation and its delivery ordering; the semantics live in observability §3.4 / §6.

## 7. Out of scope

Not covered by this specification; deferred to follow-on capabilities or proposals:

- **Middleware** — wrapping nodes with cross-cutting concerns (retry, timing, logging).
- **Checkpointing and resume** — pipeline utility, not a graph-engine primitive.
- **Parallel fan-out / fan-in** — batch execution of a single node over many inputs.
- **Streaming outputs** — per-node streaming of partial state updates.
- **Persistent state backends** — durable state stores beyond in-memory execution.
- **Human-in-the-loop interrupts** — pause, inspect, resume semantics.
