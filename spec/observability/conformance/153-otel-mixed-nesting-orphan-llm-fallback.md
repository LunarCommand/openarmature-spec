# 153 — orphan LLM-span fallback under mixed nesting (innermost-wins, OTel)

Closes the §4.3 innermost-wins arm of 0084's orphan fallback for **mixed-kind** nesting. When an orphan call is
enclosed by wrappers of different kinds — a per-branch dispatch span *and* a fan-out instance span — §4.3
resolves it to the **innermost**. 0084's shipped fixtures cover only fan-out-in-fan-out (133); this pins the
mixed case (v0.103.1 PATCH, already-normative). It complements 152 (branch dispatch as the sole wrapper) and 133
(fan-out instance as the sole wrapper).

A parallel-branches node dispatches a `work` branch (whose inner fan-out runs the orphan-issuing `guard`) and a
trivial `idle` sibling (keeping the parallel-branches node non-degenerate, ≥2 branches). The orphan's enclosing
wrappers are the outer `work` dispatch span and the inner fan-out instance span; the orphan parents under the
inner one.

**Spec sections exercised:**

- observability §4.3 / §5.5 — orphan fallback resolves to the *innermost* enclosing wrapper when wrapper kinds
  are mixed (a fan-out instance span nested inside a branch dispatch span).

**Case:**

1. `orphan_llm_call_parents_under_innermost_fan_out_instance_not_branch` — parallel-branches (`work` / `idle`) →
   `work`'s inner fan-out (1 instance) → `guard` issues a pre-phase orphan call. The orphan
   `openarmature.llm.complete` parents under the fan-out instance span (innermost), never the enclosing `work`
   dispatch span, the node spans, the invocation, or the not-yet-open `guard` node span.

**What fails:**

- Resolving the orphan to the outer `work` branch dispatch span (outermost, not innermost — the §4.3 violation),
  to a node span or the invocation, or making it a child of the `guard` node span.
