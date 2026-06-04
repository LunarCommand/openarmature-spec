# 005 — Suspend inside a subgraph propagates

A node inside a subgraph MAY call `suspend()`. The suspension
propagates: the subgraph invocation suspends, the outer node
containing the subgraph also suspends as a consequence, the entire
outer invocation suspends. Resume re-enters at the subgraph's
suspended node and continues; the outer graph's projection-out
happens normally once the subgraph completes after resume.

**Spec sections exercised:**

- §8.1 — subgraph composition: suspension propagates to the outer
  invocation.
- §7 — resume re-enters at the suspended node (under default
  `mark_node_completed=True`, continues at the node AFTER the
  suspending node inside the subgraph).

**What passes:**

- Initial invoke returns suspended with `suspending_node` reported as
  the outer subgraph wrapper.
- Resume completes; final state shows the outer pre-node ran (before
  suspend), inner_post ran (after resume, inside subgraph),
  after_subgraph ran (after subgraph completed), and the subgraph's
  output projected to the outer state.

**What fails:**

- Initial invoke returns errored or completed — would mean subgraph
  suspension did not propagate.
- Resume re-runs `pre` or `inner_pre` — would mean
  `completed_positions` did not preserve the pre-suspend execution
  trace.
- Resume re-runs `inner_suspend` — would mean the default
  `mark_node_completed=True` did not apply (would only re-run under
  `mark_node_completed=False`, covered in a future fixture).
