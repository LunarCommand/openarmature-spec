# 027 — Attempt Index Resets On Resume

Verifies §10.6: on resume, a retried node's `attempt_index` resets to `0` and the retry
budget restarts. A node whose retry budget was exhausted in the prior run gets a fresh
budget on resume — consistent with the "resume is a new execution attempt" framing.

**Spec sections exercised:**

- §10.6 Retry on resume — `attempt_index` resets to `0`; retry budget restarts.
- §10.4 step 4 — resume mints a new `invocation_id`; each attempt at completing the graph
  is its own invocation.
- Pipeline-utilities §6.1 Retry middleware — wraps the node; budget is per-invocation, not
  per-correlation-id.

**Cases:**

1. `exhausted_retry_budget_resumes_with_fresh_budget` — node wrapped with `retry middleware`
   (`max_attempts: 3`); fails 3 times on first invocation (budget exhausted; engine raises
   `node_exception`); on resume, harness mock lets it succeed on the second attempt; assert
   the successful attempt has `attempt_index == 1` (resume started fresh at 0, not carrying
   over the prior 3 attempts).

**What passes:**

- The successful resumed attempt has `attempt_index: 1`, not `attempt_index: 4` or higher.
- The retry middleware's budget is honored fresh on resume (would have failed if budget
  carried over).
- Saved record from the first run has no `completed_positions` entry for the failed node
  (every attempt failed; no successful completion to save).

**What fails:**

- `attempt_index` carries over from the prior run (resume sees the budget as already
  exhausted and the second attempt's `attempt_index` is 4 or higher).
- Retry middleware skips re-attempting because it thinks the budget is already exhausted.
- Engine treats the resumed node as if it had previously succeeded (no retries needed) when
  it actually failed every prior attempt.
