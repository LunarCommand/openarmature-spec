# 006 — Fan-Out Instance Attribution via fan_out_index

Verifies §4.3 (fan-out span hierarchy), §4.5 (fan-out instance spans share their parent
fan-out node's name), and §5.4 (fan-out span attributes). Per-instance disambiguation
relies entirely on the `openarmature.node.fan_out_index` attribute and parent-child
hierarchy — sibling instance spans intentionally share the same span name.

**Spec sections exercised:**

- §4.3 Parent-child rules — fan-out instance spans are children of the fan-out node span.
- §4.5 Span name table — fan-out instance span name = fan-out node's name in the parent graph.
- §5.4 Fan-out span attributes — `fan_out_index`, `parent_node_name` on instance spans;
  `item_count`, `concurrency`, `error_policy` on the fan-out node span.

**Cases:**

1. `three_instances_attributed_by_fan_out_index` — `[10, 20, 30]`, `concurrency: 2`,
   `error_policy: collect`. Three instance spans appear under the fan-out node span, each
   carrying its `fan_out_index` (0, 1, 2). Each instance contains its inner subgraph's
   `compute` node span.

**What passes:**

- The fan-out node span carries `item_count: 3`, `concurrency: 2`, `error_policy: "collect"`.
- Each instance span carries a unique `fan_out_index` in `0..2` and `parent_node_name: "process"`.
- Each instance span has the inner subgraph's `compute` node span as a child.

**What fails:**

- Instance spans collapsed into a single span (no per-instance attribution).
- `fan_out_index` missing, duplicated across siblings, or out of range.
- Fan-out node span missing the configuration attributes (`item_count`, `concurrency`,
  `error_policy`) — these are filterable in trace UIs and load-bearing for production debugging.
- Instance spans named after the inner subgraph (e.g., `"worker"`) instead of the fan-out
  node's name in the parent graph (`"process"`).
