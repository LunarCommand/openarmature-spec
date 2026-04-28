# 013 — Observer Subgraph Namespacing and Ordering

Verifies that observer events fire across a subgraph boundary with the correct `namespace` chain,
monotonic `step` counter, and per-event delivery order from outermost graph down to innermost.

The fixture format used here is documented in fixture 012's `.md`.

**Spec sections exercised:**

- §6 Node event shape — `namespace` is a chain of node names from the outermost graph down to the
  current node; `step` increments across subgraph-internal node executions in the same invocation.
- §6 Node event shape — `parent_states` is an ordered sequence of containing-graph state snapshots,
  outermost first. For an outermost-graph node, `parent_states` is empty; for a one-level subgraph
  node, `parent_states` is `[outer_state_at_subgraph_entry]`. The invariant
  `len(parent_states) == len(namespace) - 1` MUST hold.
- §6 Parent-state snapshot semantics — every event from a single subgraph run shares the same
  `parent_states` snapshot, since the parent is not stepping while the subgraph runs.
- §6 Event delivery — graph-attached observers are delivered outermost-first when multiple graphs
  contain the executing node; a subgraph-attached observer fires only for events from the subgraph it
  is attached to.
- §6 Observers attached to a compiled graph — fire whenever that graph runs, including as a subgraph
  inside a parent.

**What passes:**

- `obs_outer` (attached to the outer graph) receives all four events:
  `outer_in` (step 0), `inner_x` (step 1), `inner_y` (step 2), `outer_out` (step 3).
- `obs_inner` (attached to the subgraph) receives only the two subgraph-internal events (steps 1 and 2).
- Inner events have `namespace: [outer_sub, inner_x]` and `[outer_sub, inner_y]` respectively. Outer
  events have single-element namespaces.
- For each subgraph-internal event, `obs_outer` is delivered before `obs_inner` per the §6 ordering rule
  ("outermost graph down to the graph that directly owns the node").
- `pre_state` and `post_state` for inner-node events carry the subgraph's state shape (the state the
  inner node received). The subgraph runs from its own schema defaults at entry (no projection-in by
  default per §2), so `inner_x`'s `pre_state` is `{v: 0, trace: []}`, NOT the outer state at the moment
  `outer_sub` is entered.
- `parent_states` for `inner_x` and `inner_y` events is `[{v: 1, trace: ["outer_in"]}]` — the outer
  state at the moment `outer_sub` was entered, which is `outer_in`'s post-state. Both inner events
  carry the *same* snapshot.
- `parent_states` for `outer_in` and `outer_out` events is `[]` (empty) — they are outermost-graph
  events with no containing graph.
- Final outer state matches the no-observer baseline: `trace` collects `outer_in`, the subgraph's
  contributions via default field-name matching, then `outer_out`.

**What fails:**

- `obs_inner` receives an `outer_in` or `outer_out` event — subgraph-attached observers must not see
  events from outside their graph.
- `obs_outer` does not receive subgraph-internal events — outer-attached observers must see every event
  from every graph executing inside the invocation.
- For an inner event, `obs_inner` is delivered before `obs_outer` — the §6 hierarchy is reversed.
- `step` resets at the subgraph boundary instead of incrementing monotonically across it.
- `namespace` is a delimiter-joined string instead of an ordered sequence — §6 forbids string-joined
  representation at the spec boundary.
- Inner-node `pre_state`/`post_state` carry outer-state shape — the events must reflect the state the
  *node itself* received, which is subgraph state.
- An inner event's `parent_states` is empty, or carries something other than the outer state at the
  moment the subgraph was entered (e.g., an updated outer state mid-subgraph-run, or an outer state
  with the subgraph's contributions already projected back).
- An outer event has a non-empty `parent_states` — outermost-graph events have no containing graph.
- `len(parent_states) != len(namespace) - 1` — the invariant must hold for every event.
