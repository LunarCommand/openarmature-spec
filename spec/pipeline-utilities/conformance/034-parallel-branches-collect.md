# 034 — Parallel Branches Collect

Three branches with `error_policy: collect`. The middle branch raises;
the other two complete successfully. Verifies §11.5 collect semantics —
all branches run regardless of individual failures, successful contributions
merge, failures recorded in `errors_field`, parent run continues.

**Spec sections exercised:**

- §11.5 Error policy — collect mode: successful branches contribute, failed
  branches' errors are captured, the parallel-branches node returns normally.
- §11.4 Per-branch projection (out) — failed branches' `outputs` projections
  do NOT fire (`beta_result` stays at its default of 0).
- §11.1 `errors_field` configuration — implementation-defined record shape
  including at minimum `branch_name` and the error category.

**What passes:**

- Final `alpha_result == 1` and `gamma_result == 3` (successful branches
  contributed via their `outputs`).
- Final `beta_result == 0` (failed branch's `outputs` did NOT fire).
- Final `branch_errors` contains a record with `branch_name=beta` and
  `category=node_exception`.
- The graph completes (no exception propagates to the caller).

**What fails:**

- `beta_result != 0` — failed branch's `outputs` fired.
- `branch_errors` is empty — the failure wasn't recorded.
- The graph raises an exception — collect mode treats the failure as a
  recorded outcome, not an aborted run.
- alpha or gamma contribution is missing — collect mode should have applied
  both successful branches' contributions.
