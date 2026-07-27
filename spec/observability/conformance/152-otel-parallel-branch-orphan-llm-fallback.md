# 152 — orphan LLM-span fallback inside a parallel branch (OTel)

Closes the per-branch arm of 0084's §5.5 *Lineage-resolved parent* orphan fallback. The shipped orphan fixtures
(133 OTel / 134 Langfuse) exercise only the **fan-out** enclosing wrapper, but §5.5's fallback is equally
normative for the **per-branch dispatch span** — so an implementation could mis-resolve a branch-issued orphan
call and still pass every 0084 fixture. This is the parallel-branches analogue of 133 (v0.103.1 PATCH, pins
already-normative behavior).

A wrapper-issued LLM call (via `calls_llm_from_wrapper`, defined in 133's header) has no open calling-node span,
so its provider span falls back to the nearest enclosing wrapper — here the synthesized per-branch dispatch span
— routed to the correct branch by `branch_name` (the parallel-branches counterpart of 133's fan-out-index chain).

**Spec sections exercised:**

- observability §5.5 — orphan fallback resolves to the nearest enclosing wrapper; the per-branch dispatch span is
  a valid wrapper kind (not only the fan-out instance span).
- observability §4.3 / §5.7 — the synthesized per-branch dispatch span (branch_name, parent_node_name); the
  orphan span parents under it, a sibling of the branch's node span.

**Case:**

1. `orphan_llm_call_parents_under_correct_branch_dispatch_span` — two branches, each `guard` issues a pre-phase
   orphan call. Each orphan `openarmature.llm.complete` parents under its own branch's dispatch span, routed by
   `branch_name`; never the other branch's dispatch span, the dispatcher node span, the invocation, or the
   (not-yet-open) `guard` node span.

**What fails:**

- Resolving a branch-issued orphan to the dispatcher node span or invocation (fallback too shallow), to the
  wrong branch's dispatch span (branch_name mis-routing), or making it a child of the `guard` node span (which
  opens only after the pre-phase call fires).
