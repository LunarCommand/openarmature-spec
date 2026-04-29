# 010 — Middleware Subgraph Isolation

Verifies §4 strict bidirectional locality: the parent graph's per-graph middleware wraps the
subgraph as a single dispatch (does NOT see x or y individually); the subgraph's own per-graph
middleware wraps x and y but does NOT fire for outer_node.

The accumulated trace exposes both behaviors: parent.pre/post sandwiches outer_node and
sandwiches the entire sub dispatch (twice — once for each outer node). subgraph.pre/post
appears only between parent.pre and parent.post when the sub dispatch is the wrapped node, and
only inside that — never for outer_node.

**Spec sections exercised:**

- §4 Subgraph composition — strict bidirectional locality.
- §4 The parent's per-graph middleware wraps the subgraph-node dispatch.
- §4 The subgraph's own per-graph middleware wraps the subgraph's internal nodes.
- §4 No implicit propagation across the boundary.

**What passes:**

The 11-element `trace`:

```
parent.pre, outer_node, parent.post,
parent.pre, subgraph.pre, x, subgraph.post, subgraph.pre, y, subgraph.post, parent.post
```

The first three from outer_node's wrap (parent.pre/post sandwiches outer_node only). The last
eight from the sub dispatch's wrap (parent.pre/post sandwiches the whole subgraph; subgraph.pre/post
sandwiches each inner node individually, then projects out via field-name matching).

Final `v` is 20 (subgraph's last write to v projects via field-name matching; outer_node's
v=1 is overwritten by last_write_wins).

**What fails:**

- parent.pre/post appears around `x` or `y` individually — outer middleware leaked into subgraph
  internals (cross-boundary propagation, violating §4).
- subgraph.pre/post appears around `outer_node` — subgraph middleware reached the parent
  (impossible by spec, indicates wrong scoping).
- Parent middleware fires only once for sub instead of being part of each subgraph-internal node
  invocation — the implementation isn't wrapping the dispatch atomically.
- Final v is 1 (subgraph projection didn't happen) or 0 (outer_node didn't run).
