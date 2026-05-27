# 031 — Langfuse Subgraph Span Observation Hierarchy

Verifies §8.3 row 3 (Subgraph span → Span observation) and §8.4.2 subgraph-related
attribute-mapping rules for the Langfuse mapping. Mirrors the OTel-side fixture
`002-otel-subgraph-hierarchy` one-to-one in graph topology; the assertion surface is the
Langfuse Trace / Observation tree rather than the OTel span tree.

**Spec sections exercised:**

- §8.3 row 3 — Subgraph span maps to a Span observation, child of the surrounding parent
  Span (or, for a top-level subgraph dispatched directly from the invocation, child of
  the Trace itself, since per §8.3 row 1 the invocation maps to the Trace rather than to
  a root Span observation).
- §8.4.2 — `openarmature.node.namespace` maps to `observation.metadata.namespace`
  (string array preserved as-is); `openarmature.subgraph.name` maps to
  `observation.metadata.subgraph_name` when present (set on the subgraph's nested node
  observations per the subgraph-span attribute rules).
- §8.4.1 / §8.5 — `correlation_id` cross-cutting consistency on Trace metadata and on
  every Observation metadata.

**Graph topology:** outer graph with three nodes (`outer_in`, `outer_sub`, `outer_out`);
`outer_sub` is a subgraph dispatch to an `inner` subgraph containing two nodes
(`inner_x`, `inner_y`).

**What passes:**

- `outer_in`, `outer_sub`, `outer_out` are all Span observations directly under the
  Trace (the invocation maps to the Trace; no root Span observation wraps them).
- `inner_x` and `inner_y` are Span observations under `outer_sub` (the subgraph
  wrapper contains the inner nodes).
- The `outer_sub` subgraph dispatch observation carries
  `metadata.subgraph_name = "inner"` per §8.4.2 (sourced from
  `openarmature.subgraph.name` on the subgraph span itself per §5.3).
  The inner-node observations (`inner_x`, `inner_y`) do NOT carry
  `subgraph_name` — that attribute is subgraph-span-scoped, not
  inner-node-scoped.
- `metadata.namespace` on each observation reflects the subgraph nesting:
  `["outer_in"]`, `["outer_sub"]`, `["outer_sub", "inner_x"]`, `["outer_sub", "inner_y"]`,
  `["outer_out"]`.
- The Trace's `metadata.correlation_id` matches every Observation's
  `metadata.correlation_id` (cross-cutting consistency per §8.5).
- The Trace's `id` equals the invocation's `invocation_id` per §8.4.1.

**What fails:**

- Inner-subgraph nodes appear as direct children of the Trace rather than nested under
  `outer_sub` — subgraph parenting is collapsed.
- `metadata.subgraph_name` missing from the `outer_sub` subgraph dispatch observation —
  §8.4.2 subgraph-name propagation from the subgraph span not implemented.
- `metadata.subgraph_name` set on inner-node observations rather than on the subgraph
  dispatch — attribute scope mis-routed (subgraph-span attribute per §5.3, not a
  per-node attribute).
- `metadata.namespace` on inner-node observations is flat rather than reflecting the
  subgraph dispatch (e.g. `["inner_x"]` instead of `["outer_sub", "inner_x"]`).
- `correlation_id` differs between the Trace and any of the Observations — cross-cutting
  consistency broken.
