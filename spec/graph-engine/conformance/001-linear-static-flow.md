# 001 — Linear Static Flow

Verifies the base execution model: three nodes connected by static edges executing in declared order, with
partial updates merged into state and `END` halting the run.

**Spec sections exercised:**
- §2 Node — partial update returned from each node.
- §2 Edge — static edges.
- §2 END — halt on reaching the sentinel.
- §3 Execution model — steps 1–5.

**What passes:**
- Node-execution order is `[a, b, c]`.
- `greeting` holds the last-write-wins value (`"hello world"`).
- `log` holds the `append`-merged list in order (`["a", "b", "c"]`).

**What fails:**
- Any out-of-order execution.
- Nodes continuing to run past `END`.
- `append` reducer overwriting instead of concatenating.
