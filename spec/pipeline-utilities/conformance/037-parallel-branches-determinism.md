# 037 — Parallel Branches Determinism

Three branches with intentionally varying inner-node completion timing
(50ms, 5ms, 25ms). Branches alpha and beta both write to the same parent
field (`merged_dict`) via the `merge` reducer. Verifies §11.8 — branch
dispatch order on the observer stream AND the parent-field merge order are
both deterministic on branch insertion order, regardless of completion
timing.

**Spec sections exercised:**

- §11.8 Determinism — branch dispatch order matches the `branches`
  mapping's insertion order, not completion order. Branch fan-in (§11.4)
  applies contributions in insertion order.
- §11.4 Per-branch projection (out) — when two branches write the same
  parent field, the parent's reducer applies contributions in branch
  insertion order; for `merge` reducer, later branches' keys override
  earlier ones.
- Cross-cutting graph-engine §5 determinism: scheduler nondeterminism
  affects timing but NOT state.

**What passes:**

- `merged_dict == {key: "beta_value"}` — alpha contributed
  `{key: "alpha_value"}` first, then beta's `{key: "beta_value"}` merged
  over it (insertion order, not completion order).
- `gamma_result == 42`.
- Observer events for branch dispatch fire in order: alpha, beta, gamma —
  matching `branches` insertion order despite beta's inner node
  completing first.

**What fails:**

- `merged_dict == {key: "alpha_value"}` — would mean the engine merged in
  completion order (beta finishing first, alpha overriding it later).
- Observer events fire in completion order rather than insertion order.
