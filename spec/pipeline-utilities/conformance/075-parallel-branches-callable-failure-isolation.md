# 075 — Parallel branches: per-leg failure-isolation on a callable branch

Verifies that §11.7 branch middleware composes with the inline-callable branch
form (proposal 0075): a `call` branch wrapped in `FailureIsolationMiddleware`
degrades on failure and emits a `FailureIsolatedEvent`, while the sibling branch
completes. Per-leg isolation is the existing §11.7 contract — no new per-leg
config. Counterpart to fixture 064 case 2 (isolation on a subgraph branch).

## Spec coverage

- §11.7 — branch middleware (`FailureIsolationMiddleware`) on a callable branch;
  partial / degraded contribution.
- §11.1.1 — a `call` branch carries `middleware` like a subgraph branch.
- §6.3 / proposal 0068 — `caught_exception.category` resolves through carriers to
  the originating `provider_unavailable`.

## Case

`callable_branch_failure_isolated_and_degraded` — the `vector` callable raises
`provider_unavailable`; its branch `FailureIsolationMiddleware` catches it,
degrades to `vector_result: -1`, and emits a `FailureIsolatedEvent`
(`event_name: "vector_isolated"`, `caught_exception.category:
provider_unavailable`). The `fts` branch completes normally (`fts_result: 2`).
The degraded branch does not "fail" from the node's view, so `fail_fast` is not
triggered and the sibling is not cancelled.

## Anti-cases (would indicate a broken implementation)

- The callable branch's failure isn't caught — `call` branches don't compose
  with §11.7 branch middleware.
- No `FailureIsolatedEvent` fires — the degrade isn't observable.
- `caught_exception.category` is `node_exception` (a masking carrier) rather than
  the originating `provider_unavailable`.
- The sibling `fts` branch is cancelled or lost — the degraded leg wrongly
  tripped `fail_fast`.
