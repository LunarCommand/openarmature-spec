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
- `metadata.step` values follow graph-engine §6's shared-counter rule across subgraph
  dispatch: `outer_in=0`, `inner_x=1`, `inner_y=2`, `outer_out=3`. The global counter
  increments for every node execution including subgraph-internal nodes; it does NOT
  reset at the subgraph boundary. The `outer_sub` wrapper observation, which does not
  itself execute (wrappers don't emit events), synthesizes its `step` value from the
  first inner event's step (= 1, matching `inner_x`).
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
- `metadata.step` resets at the subgraph boundary (e.g. `outer_out=1` or `outer_out=2`
  instead of `outer_out=3`) — implementation's step counter is sub-scoped rather than
  shared across subgraph descents, contradicting §6's "subgraph-internal node executions
  increment the same counter" rule.
- `correlation_id` differs between the Trace and any of the Observations — cross-cutting
  consistency broken.
