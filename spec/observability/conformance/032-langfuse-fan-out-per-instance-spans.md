# 032 — Langfuse Fan-Out Per-Instance Spans (Non-Detached)

Verifies §8.3 rows 4-5 (Fan-out node → Span observation dispatch container; Fan-out
instance → Span observation child of the dispatch) and §8.4.2 fan-out-related
attribute-mapping rules for the Langfuse mapping. Mirrors the OTel-side fixture
`006-otel-fan-out-instance-attribution` one-to-one in graph topology.

**Spec sections exercised:**

- §8.3 row 4 — Fan-out node span maps to a Span observation (the dispatch container).
- §8.3 row 5 — Fan-out instance span maps to a Span observation, child of the fan-out
  node's Span observation.
- §8.4.2 fan-out-node-specific keys — `openarmature.fan_out.item_count` /
  `concurrency` / `error_policy` map to `observation.metadata.fan_out_item_count` /
  `fan_out_concurrency` / `fan_out_error_policy` on the dispatch observation only.
- §8.4.2 fan-out-instance-specific keys — `openarmature.node.fan_out_index` /
  `openarmature.fan_out.parent_node_name` map to `observation.metadata.fan_out_index`
  and `observation.metadata.fan_out_parent_node_name` on each per-instance observation.
- §8.4.1 / §8.5 — `correlation_id` cross-cutting consistency on Trace and every
  Observation metadata.

**Graph topology:** single fan-out node (`process`) dispatching three instances over a
one-node `worker` subgraph (the `compute` node), non-detached, `concurrency: 2`,
`error_policy: collect`.

**What passes:**

- One dispatch Span observation named `process` under the Trace, carrying
  `metadata.fan_out_item_count = 3`, `metadata.fan_out_concurrency = 2`,
  `metadata.fan_out_error_policy = "collect"`.
- Three per-instance Span observations under the dispatch, each with a unique
  `metadata.fan_out_index` in `0..2` and `metadata.fan_out_parent_node_name = "process"`.
- Each per-instance observation carries `metadata.subgraph_name = "worker"` per §5.3 +
  §8.4.2 (the per-instance dispatch IS a subgraph span — it dispatches the worker
  subgraph for one fan-out item, so it carries both fan-out-instance attributes and the
  subgraph wrapper's `subgraph.name`).
- Each per-instance observation has a single child Span observation `compute` (the
  worker subgraph's single inner node). `compute` is a regular node, so it does NOT
  carry `subgraph_name`.
- The Trace's `metadata.correlation_id` matches every Observation's
  `metadata.correlation_id`.

**What fails:**

- Per-instance observations parent to the Trace directly rather than to the dispatch
  observation — fan-out dispatch hierarchy collapsed.
- Fan-out-node-specific keys (`fan_out_item_count` / `fan_out_concurrency` /
  `fan_out_error_policy`) appear on per-instance observations, or are missing from the
  dispatch observation — node-vs-instance attribute scoping violated.
- `fan_out_index` is missing, duplicated, or out of `0..count-1` range — per-instance
  attribution broken.
- `fan_out_parent_node_name` missing on per-instance observations — instance-to-parent
  linkage lost.
