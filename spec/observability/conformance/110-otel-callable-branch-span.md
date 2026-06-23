# 110 — OTel callable-branch dispatch spans (+ skip emits none)

Verifies observability §5.7's callable-branch span rendering (proposal 0075). An inline-callable
parallel branch renders as a per-branch dispatch span keyed by `openarmature.node.branch_name`, with
**no inner-node spans** beneath it (the branch is the single unit). A `when`-skipped branch produces
**no span**. Pins the §5.7 callable / skipped span shape that 0075 specified but left unfixtured.

**Spec sections exercised:**

- observability §5.7 — callable-branch dispatch span keyed by `openarmature.node.branch_name` +
  `openarmature.parallel_branches.parent_node_name`, with no inner-node spans; a `when`-skipped
  branch emits no span.
- pipeline-utilities §11.1.1 / §11.10 — inline-callable `call` branches + the `when` dispatch skip.

**Cases:**

1. `callable_branches_render_keyed_spans_skipped_emits_none` — node `retrieve` with callable branches
   `vector` (`when run_vector`, defaults false → skipped), `fts`, and `keyword` (both dispatch). The
   two dispatched branches each render one keyed dispatch span (`children: []`); the skipped `vector`
   branch produces no span.

**What passes:**

- One dispatch span per dispatched callable branch, keyed by `branch_name` with `parent_node_name`,
  no inner-node children.
- No span for the `when`-skipped branch.

**What fails:**

- A callable branch renders inner-node spans (treating it like a subgraph branch).
- The skipped branch still emits a span.
- A dispatch span is not keyed by `branch_name` or is missing `parent_node_name`.

> Note: `openarmature.parallel_branches.branch_count = 2` is asserted here — the **dispatched** count
> (`vector` is `when`-skipped; `fts` + `keyword` dispatch). The graph-engine §6 / observability §5.7
> reconciliation confirms `branch_count` is the dispatched subset under a `when`-skip (`branch_names`
> stays the full declared set), so the value is unambiguous.
