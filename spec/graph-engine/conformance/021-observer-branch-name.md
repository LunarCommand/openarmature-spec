# 021 — Observer Branch Name

Verifies the new `branch_name` field on `NodeEvent` (added by proposal
0011 to graph-engine §6) is correctly populated on events from nodes
inside a parallel-branches branch and ABSENT on events from outermost-graph
nodes.

A simple linear graph wraps a parallel-branches dispatch between two
outer-graph nodes. The observer captures every event; assertions cover
both populated-and-absent cases.

**Spec sections exercised:**

- §6 NodeEvent — the new `branch_name` field; populated only on events
  from nodes inside a parallel-branches branch (per pipeline-utilities §11).
- §6 NodeEvent uniqueness invariant — `branch_name` participates in the
  identifier tuple `(namespace, branch_name, fan_out_index, attempt_index, phase)`.

**What passes:**

- Outermost-graph node events (`outer_pre`, `dispatcher`, `outer_post`)
  have `branch_name` absent.
- Branch alpha's inner node `a` events carry `branch_name == "alpha"`.
- Branch beta's inner node `b` events carry `branch_name == "beta"`.

**What fails:**

- Outermost events have `branch_name` populated (the dispatcher node itself
  has no `branch_name` — only its inner branch contents do).
- Inner branch events have `branch_name` absent (the field wasn't
  propagated down the namespace chain).
- The wrong branch_name is attached (e.g., `"beta"` on alpha's inner
  events).
