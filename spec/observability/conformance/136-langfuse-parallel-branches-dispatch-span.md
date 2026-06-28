# 136 — Langfuse Parallel-Branches Dispatch Span (Per-Branch)

Verifies the Langfuse parallel-branches dispatch-span synthesis (proposal 0088): the Langfuse
observer renders the same three-level Observation subtree the OTel observer produces — the
parallel-branches NODE Span observation, a synthesized per-branch dispatch Span observation for
each branch, and the branch's inner-node observations beneath it. The Langfuse analog of the
fan-out fixture `032-langfuse-fan-out-per-instance-spans`, and the parallel-branches analog of the
OTel-side `038-otel-parallel-branches-dispatch-span` (the cross-backend reference shape this tree
must match). Before 0088 the Langfuse tree was pinned only incidentally by the §3.4 caller-metadata
fixture `030`; this fixture is its first-class dedicated pin.

**Spec sections exercised:**

- §8.3 — Parallel-branches node span maps to a Span observation (the container of the per-branch
  dispatch Spans); per-branch dispatch span maps to a Span observation, child of the
  parallel-branches node Span (one per `branch_name`), with `observation.name` = the `branch_name`.
- §8.4.8 — the Langfuse observer synthesizes the per-branch dispatch Span observation, mirroring
  the OTel §4.3 / §6 synthesis; the synthesized Span's `observation.name` is the `branch_name`.
- §8.4.2 — `openarmature.parallel_branches.branch_count` / `error_policy` map to
  `observation.metadata.parallel_branches_branch_count` / `parallel_branches_error_policy` on the
  parallel-branches node Span observation only; `openarmature.parallel_branches.parent_node_name`
  maps to `observation.metadata.parallel_branches_parent_node_name` on each per-branch dispatch
  Span observation only; `branch_name` (per proposal 0042) maps to `observation.metadata.branch_name`
  on the per-branch Span observation and propagates onto its inner observations.
- §5.7 — the parallel-branches span-attribute surface (`branch_count` / `error_policy` on the node
  span; `branch_name` / `parent_node_name` on the dispatch span; `branch_name` on every inner-node
  observation beneath the dispatch span).
- §8.4.1 / §8.5 — `correlation_id` cross-cutting consistency on the Trace and every Observation
  metadata.

**Graph topology:** single parallel-branches node (`dispatcher`) dispatching two named branches —
`fraud_check` and `policy_audit` — each a one-node `ask` subgraph that makes an LLM call.
`error_policy: fail_fast`.

**What passes:**

- One Span observation named `dispatcher` (the parallel-branches NODE span) under the Trace,
  carrying `metadata.parallel_branches_branch_count = 2` and
  `metadata.parallel_branches_error_policy = "fail_fast"`.
- Two per-branch dispatch Span observations under `dispatcher`, each named for its branch
  (`observation.name` = `fraud_check` / `policy_audit`), each carrying
  `metadata.branch_name` matching its name and
  `metadata.parallel_branches_parent_node_name = "dispatcher"`.
- Each dispatch Span has a single child `ask` Span observation carrying `metadata.branch_name`
  matching its branch, and that `ask` Span has a single child Generation observation
  (`openarmature.llm.complete`) likewise carrying the branch's `branch_name`.
- The Trace's `metadata.correlation_id` matches every Observation's `metadata.correlation_id`.

**What fails:**

- The inner `ask` / Generation observations parent directly under the `dispatcher` node Span rather
  than under their per-branch dispatch Span — dispatch-span synthesis collapsed, and same-named
  inner `ask` observations (one per branch) lose their structural disambiguation.
- A per-branch dispatch Span observation's `observation.name` is not the `branch_name` (e.g. it
  reuses the parent `dispatcher` name) — §8.3 / §8.4.8 naming violated.
- The node-span-specific keys (`parallel_branches_branch_count` / `parallel_branches_error_policy`)
  appear on a per-branch dispatch Span, or the dispatch-span-specific key
  (`parallel_branches_parent_node_name`) appears on the node Span — node-vs-dispatch attribute
  scoping violated.
- A per-branch dispatch Span or its inner observations are missing `branch_name`, or carry the
  sibling branch's `branch_name` — per-branch attribution broken.
- `correlation_id` is missing from the Trace metadata or any Observation metadata, or differs
  across them.
