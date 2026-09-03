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

## Why `yield_after_call: true`

Every case here carries `yield_after_call: true` (conformance-adapter §5.1, proposal 0124). Without it
the wrapper returns immediately after the provider call, so whether the enclosing dispatch span exists
when the orphan resolves is decided by the observer's architecture rather than by the spec.

An observer that registers spans in the engine's execution path has already materialized the wrapper
span and passes. An observer that does its work on the delivery queue has not, and under the pre-0124
trigger it had no span to parent under. Both were conforming, and this fixture could not tell them
apart, so it passed on a favourable interleaving rather than on the rule.

The directive forces the interleaving that separates them: observer delivery queued before the wrapper
returns makes progress first. Combined with §6's amended trigger, which synthesizes the dispatch span
on the first event that needs it, and §5.5's *Resolution is structural*, the correct parent is now
reachable and the wrong one is now failing rather than merely unlucky.

No assertion changed. This fixture already asserted the parent §5.5 mandates; what changed is that it
can now fail an implementation that gets there by accident.
