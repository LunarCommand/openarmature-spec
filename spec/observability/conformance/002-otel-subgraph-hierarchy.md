# 002 — OTel Subgraph Hierarchy

Verifies §4 Span hierarchy and §4.5 Span names for nested subgraphs: the subgraph dispatch
produces a subgraph span (named after the SubgraphNode in the parent), with inner-node spans as
its children. The chained `namespace` on inner-node spans matches the §4.3 parent-child rule.

**Spec sections exercised:**

- §4 Span hierarchy — invocation → outer nodes → subgraph span → inner nodes → outer node.
- §4.3 Parent-child rules — namespace `[outer_sub, inner_x]` parents to the subgraph span for
  `outer_sub`.
- §4.5 Span names — subgraph span name = SubgraphNode's name in the parent (`outer_sub`).

**What passes:**

- Five spans total: invocation, outer_in, outer_sub, outer_out, plus inner_x and inner_y as
  children of outer_sub.
- Subgraph span is named `"outer_sub"` (the SubgraphNode's name in the parent).
- Inner-node spans have `openarmature.node.namespace == ["outer_sub", "inner_x"]` etc.
- Hierarchy: invocation → {outer_in, outer_sub, outer_out}; outer_sub → {inner_x, inner_y}.

**What fails:**

- Inner-node spans are siblings of outer nodes (parent-child rule broken).
- Subgraph span named `"openarmature.subgraph"` or similar constant (per §4.5 it must be the
  SubgraphNode's name).
- Inner-node `namespace` is just `["inner_x"]` instead of the chained `["outer_sub", "inner_x"]`.
