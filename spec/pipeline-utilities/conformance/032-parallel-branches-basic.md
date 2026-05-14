# 032 — Parallel Branches Basic

Smallest possible parallel-branches: three heterogeneous subgraphs (different
state schemas) writing to three disjoint parent fields. Establishes the
fundamental shape before testing nuances in 033-038.

**Spec sections exercised:**

- §11.1 Configuration — `branches` mapping with three branches.
- §11.1.1 Branch spec — `subgraph` + `outputs` per branch; no `inputs`, no
  `middleware`, no shared fields.
- §11.2 Per-branch projection (in) — branches start from subgraph defaults
  (no `inputs` declared).
- §11.3 Concurrent execution — all three branches dispatch simultaneously.
- §11.4 Per-branch projection (out) — buffered contributions apply to
  disjoint parent fields after all branches complete.
- §11.8 Determinism — outer execution order treats the parallel-branches
  node as a single dispatch.

**What passes:**

- All three branches run.
- Final state has `alpha_result=1`, `beta_result=2`, `gamma_result=3`.
- `execution_order` is `[dispatcher]` — the inner branch nodes don't appear
  at the outer-graph level (the parent sees the parallel-branches node as
  one dispatch, matching §11.6).

**What fails:**

- Any of `alpha_result`, `beta_result`, `gamma_result` not at expected value.
- Fewer or more than three branches dispatch.
- `execution_order` shows inner branch nodes (it shouldn't — the parent sees
  the parallel-branches node as one dispatch).
