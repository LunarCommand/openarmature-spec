# 038 — OTel Parallel-Branches Dispatch Span Synthesis

Verifies §4.3, §5.7, and §6 (proposal 0044): the OTel observer synthesizes a per-branch dispatch
span between the parallel-branches NODE span and each branch's inner-node spans, matching the
Langfuse fixture 030 shape on the OTel side. Inner-branch spans parent under the synthesized
dispatch span, not the parallel-branches NODE span directly.

**Spec sections exercised:**

- §4.3 *Parent-child rules* — inner-branch spans parent under the per-branch dispatch span
  (one per `branch_name` value within the parallel-branches NODE's execution).
- §5.7 *Parallel-branches span attributes* —
  `openarmature.parallel_branches.branch_count` and
  `openarmature.parallel_branches.error_policy` on the parallel-branches NODE span;
  `openarmature.node.branch_name` and `openarmature.parallel_branches.parent_node_name` on each
  per-branch dispatch span; `openarmature.node.branch_name` propagated onto every inner-node
  span beneath the dispatch span.
- §6 *Driving span lifecycle* — span-stack key includes `branch_name` (disambiguates concurrent
  inner spans across branches); lazy synthesis of per-branch dispatch span on the first inner
  event of each branch; close on parent `completed` in declaration order, children-before-parents.

**Cases:**

1. `parallel_branches_dispatch_span_synthesized_per_branch` — two-branch parallel-branches node
   (`dispatcher` with `fraud_check` / `policy_audit`), each branch with an `ask` inner LLM node.

**Harness extensions:**

- `nodes.<name>.parallel_branches.branches` — declaration of the parallel-branches branches
  (mapping from branch name to subgraph reference, per pipeline-utilities §11.1).
- `nodes.<name>.parallel_branches.error_policy` — `"fail_fast"` or `"collect"` per §11.5.
- `expected.span_tree[*].attributes.openarmature.parallel_branches.*` — assertion on the §5.7
  attribute family on the relevant span.
- `expected.span_tree[*].attributes.openarmature.node.branch_name` — assertion that the §5.2
  per-branch attribute appears on inner spans inside a parallel-branches branch (newly
  introduced by 0044).
- `invariants.same_named_inner_spans_disambiguated_by_dispatch_parent: bool` — harness asserts
  that two same-named inner spans across concurrent branches are distinguished by parent
  (their distinct dispatch spans), not by an internal observer stack-key recovery.
- `invariants.dispatch_spans_close_before_node_span: bool` — harness asserts dispatch spans'
  `ended_at` precedes the parallel-branches NODE span's `ended_at`.
- `invariants.dispatch_spans_close_in_declaration_order: list[str]` — harness asserts the
  declared close order of the dispatch spans matches `parallel_branches_config.branch_names`.

**What passes:**

- The OTel trace tree has two synthesized dispatch spans (one per branch), each as a child of
  the `dispatcher` parallel-branches NODE span and each parent to that branch's `ask` inner span.
- The `dispatcher` NODE span carries `openarmature.parallel_branches.branch_count = 2` and
  `openarmature.parallel_branches.error_policy = "fail_fast"`.
- Each dispatch span carries `openarmature.node.branch_name` matching its branch and
  `openarmature.parallel_branches.parent_node_name = "dispatcher"`.
- Inner `ask` spans and the nested `openarmature.llm.complete` span both carry
  `openarmature.node.branch_name` matching their branch.
- Same-named inner spans across the two branches are disambiguated by their distinct dispatch-
  span parents (no stack-key collision).
- Dispatch spans close before the parallel-branches NODE span; close order matches
  declaration order.

**What fails:**

- Inner-branch spans parent directly under the `dispatcher` NODE span (synthesis didn't happen).
- The parallel-branches NODE span lacks `branch_count` or `error_policy`.
- Dispatch spans lack `branch_name` or `parent_node_name`.
- Same-named inner spans collide on the observer's stack key (spans dictionary overwritten).
- Dispatch spans close after the parallel-branches NODE span (parents-before-children).
- Dispatch span close order doesn't match `parallel_branches_config.branch_names` declaration
  order.
