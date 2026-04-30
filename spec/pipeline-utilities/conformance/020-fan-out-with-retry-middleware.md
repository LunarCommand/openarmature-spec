# 020 — Fan-Out with Retry Middleware

Verifies that retry middleware on individual nodes inside a fan-out instance retries within that
instance only — siblings are not affected. Per-attempt observer events from inner instances
carry both `attempt_index` (per pipeline-utilities §6.1) and `fan_out_index` (per graph-engine
§6 from this proposal).

**Spec sections exercised:**

- §9.6 Composition with middleware — per-node middleware on inner-subgraph nodes wraps each
  per-instance node call.
- §6.1 Retry — independent retry budgets per instance.
- graph-engine §6 — inner events carry pair-model `phase`, plus `attempt_index` AND
  `fan_out_index` populated.

**What passes:**

- Each instance's flaky inner node fails once and succeeds on its second attempt.
- Final `scores == [10, 20, 30]` — all three instances eventually succeed.
- Per-instance retries don't delay siblings beyond the concurrency budget.
- Inner-node observer events carry `fan_out_index` 0/1/2 (matching instance index) and
  `attempt_index` 0 (failure) or 1 (success).
- Each attempt produces a started/completed pair (4 events per instance × 3 instances = 12 inner
  events).

**What fails:**

- One instance's retry blocks others (concurrency wasn't honored or instances were sequenced).
- Inner events lack `fan_out_index`.
- Inner events have all `attempt_index == 0` (retry didn't fire OR retry fired but observer
  events didn't reflect the attempts).
- Pair model not honored (only one event per attempt instead of two).
