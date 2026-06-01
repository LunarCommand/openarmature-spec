# 045 — `get_invocation_metadata()` per-attempt scoping under retry

Verifies §3.4's *Read access* per-attempt scoping under retry middleware
(pipeline-utilities §6.1). Each retry attempt sees only the metadata set during that attempt
plus the ancestor / pre-attempt baseline; writes from a prior attempt that subsequently failed
do NOT carry over to the next attempt.

**Spec sections exercised:**

- §3.4 *Read access* — *Per-attempt scoping* paragraph; reads on attempt N+1 do not see
  attempt N's writes if attempt N failed.
- pipeline-utilities §6.1 — Retry middleware behavior; per-attempt context isolation.

**Cases:**

1. `retry_attempt_does_not_see_prior_failed_attempt_writes` — A node configured with retry
   middleware (max 2 attempts; classifier accepts the test-specific transient error). On
   attempt 0: write `attempt_marker: "first"`, then raise a transient error to trigger retry.
   On attempt 1: capture the read into a state field (asserting `attempt_marker` is NOT
   present), then write `attempt_marker: "second"` and succeed. A downstream node captures the
   read and asserts `attempt_marker: "second"`.

**What passes:**

- Attempt 1's read does NOT contain `attempt_marker: "first"` (prior failed attempt's writes
  are discarded with the attempt).
- Attempt 1's write of `attempt_marker: "second"` is visible to the downstream node.
- The caller baseline (`tenantId`) is visible across all attempts.

**What fails:**

- Attempt 1's read contains `attempt_marker: "first"` (prior failed attempt's writes leaked —
  retry middleware did not isolate per-attempt copies).
- The downstream node sees `attempt_marker: "first"` instead of `"second"` (attempt-1 write
  overwritten incorrectly, or retry middleware did not commit attempt-1's writes on success).
