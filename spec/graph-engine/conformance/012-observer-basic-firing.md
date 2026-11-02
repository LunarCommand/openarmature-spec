# 012 — Observer Basic Firing

Verifies that observer hooks fire once per node execution on a linear graph and that per-event delivery
order respects the §6 hierarchy: graph-attached observers are delivered before invocation-scoped
observers, within a single event.

The observer fixture format is defined in conformance-adapter §5.5 (`observers:`) and §5.8
(`observer_events`, `delivery_order`).

**Spec sections exercised:**

- §6 Observer hooks — registration modes (graph-attached, invocation-scoped); event delivery is strictly
  serial across the entire invocation; per-event delivery order is graph-attached first, then
  invocation-scoped.
- §6 Node event shape — `step` is monotonic from `0`; `namespace` is `[node_name]` for outermost-graph
  nodes; `pre_state`/`post_state` reflect the state before and after the reducer merge.

**What passes:**

- `obs_graph` and `obs_invoke` each receive exactly six events: a `started` and a `completed` event
  per node.
- Each event has the expected `step`, `namespace`, `pre_state` and an empty `parent_states`, and each
  `completed` event has the expected `post_state`.
- For every step, `obs_graph`'s event is delivered before `obs_invoke`'s event (per `delivery_order`).
- The graph run completes; `final_state` and `execution_order` match the no-observer baseline.

**What fails:**

- Either observer receives fewer or more than six events.
- `step` does not start at 0 or is not monotonic.
- `namespace` includes anything other than `[node_name]` (e.g., a leading graph name, or a string-joined
  representation).
- An invocation-scoped observer is delivered before a graph-attached observer for the same event.
- `pre_state` reflects post-merge state (or vice versa).
