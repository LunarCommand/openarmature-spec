# 012 — Observer Basic Firing

Verifies that observer hooks fire once per node execution on a linear graph and that per-event delivery
order respects the §6 hierarchy: graph-attached observers are delivered before invocation-scoped
observers, within a single event.

This fixture also introduces the **observer fixture format** that fixtures 013–015 reuse. See "Fixture
format additions" below.

**Spec sections exercised:**

- §6 Observer hooks — registration modes (graph-attached, invocation-scoped); event delivery is strictly
  serial across the entire invocation; per-event delivery order is graph-attached first, then
  invocation-scoped.
- §6 Node event shape — `step` is monotonic from `0`; `namespace` is `[node_name]` for outermost-graph
  nodes; `pre_state`/`post_state` reflect the state before and after the reducer merge.

**What passes:**

- `obs_graph` and `obs_invoke` each receive exactly three events (one per node).
- Each event has the expected `step`, `namespace`, `pre_state`, and `post_state`.
- For every step, `obs_graph`'s event is delivered before `obs_invoke`'s event (per `delivery_order`).
- The graph run completes; `final_state` and `execution_order` match the no-observer baseline.

**What fails:**

- Either observer receives fewer or more than three events.
- `step` does not start at 0 or is not monotonic.
- `namespace` includes anything other than `[node_name]` (e.g., a leading graph name, or a string-joined
  representation).
- An invocation-scoped observer is delivered before a graph-attached observer for the same event.
- `pre_state` reflects post-merge state (or vice versa).

## Fixture format additions

The observer-related keys introduced here extend the v0 fixture format documented in the conformance
README. They are used in fixtures 012–015.

```yaml
observers:
  - name: <observer_id>          # used to key the events listing in `expected`
    attach: graph | invocation   # registration mode; "graph" attaches to the compiled
                                 # graph, "invocation" passes to invoke()
    target: outer | <subgraph_name>
                                 # which graph the observer is attached to.
                                 # "outer" = outermost graph (the one being invoked).
                                 # A subgraph name attaches the observer to that
                                 # subgraph's compiled instance.
    behavior: record | raise     # "record" stores received events for assertion;
                                 # "raise" raises on every event (used in 015 to
                                 # verify error isolation). A "raise" observer's
                                 # received events are not enumerated in `expected`.

expected:
  observer_events:
    <observer_id>:
      - step: <int>              # monotonic across the invocation, starting at 0
        node_name: <string>
        namespace: [<string>, ...]
        pre_state:  {<field>: <value>, ...}   # state before the reducer merge
        post_state: {<field>: <value>, ...}   # state after the reducer merge,
                                              # OR omit and provide `error:` for a
                                              # failed-node event (see fixture 014)
        error: <category_identifier>          # one of §4 categories, e.g.,
                                              # node_exception. Mutually exclusive
                                              # with post_state.
        parent_states:                        # OPTIONAL. Ordered sequence of
                                              # containing-graph state snapshots,
                                              # outermost first. Omitted = empty.
                                              # MUST satisfy
                                              # len(parent_states) == len(namespace) - 1.
          - {<field>: <value>, ...}           # outermost containing graph
          - {<field>: <value>, ...}           # next-inner containing graph (if nested)
          ...
      ...

  delivery_order:                # per-event delivery sequence as (observer, step)
    - {observer: <observer_id>, step: <int>}
    ...
```

The harness MUST `await drain` on the compiled graph after `invoke()` returns and before asserting on
observer state, per §6 Drain.
