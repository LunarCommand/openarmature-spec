# 074 — Parallel branches: conditional `when`

Verifies §11.10 conditional branches (proposal 0075): an optional `when`
predicate on a branch spec, evaluated once at dispatch. `false` skips the branch
(no dispatch, no contribution, no events/span); `true` (or absent) dispatches
normally. Lets "skip the vector leg when there is no embedding" be expressed
directly, without an always-run self-no-op branch.

## Spec coverage

- §11.10 — `when` predicate; skip semantics.
- §11.4 — a skipped branch contributes nothing (its parent fields keep prior /
  default values).
- §11.8 — dispatched branches retain insertion-order determinism; skipping is a
  runtime decision over the declared set.

## Cases

1. `when_false_skips_branch` — `run_vector` defaults false, so the `vector`
   branch is skipped (`vector_result` stays `0`, no event); `fts` (no `when`)
   runs → `fts_result: 2`.
2. `when_true_dispatches_branch` — `run_vector: true`, so `vector` dispatches
   alongside `fts`; both contribute (`vector_result: 1`, `fts_result: 2`).

## Anti-cases (would indicate a broken implementation)

- A `when`-false branch dispatches anyway (contributes / emits events) — the
  predicate isn't gating dispatch.
- A `when`-false branch raises instead of being cleanly skipped.
- The conditional can only be expressed via an always-run no-op branch — `when`
  isn't supported.
