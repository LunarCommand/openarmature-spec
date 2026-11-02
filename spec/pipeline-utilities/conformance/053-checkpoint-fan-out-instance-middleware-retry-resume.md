# 053 — Checkpoint Fan-Out Instance-Middleware Retry Resume

Verifies §10.11.3's composition of per-instance resume with retry
middleware applied at the instance level. A retry-exhausted instance
saved as `in_flight` re-runs on resume with a fresh retry budget
(`attempt_index` reset to 0 per §10.6). `flaky_per_index` raises
`provider_unavailable` here, a transient category the default classifier
retries (§6.1), so instance 2's three attempts exhaust on the first run.
Instance 2 is the last of three serially dispatched instances, so no
sibling can start while it fails, and the first run's attempt count is
fixed.

**Spec sections exercised:**

- §10.11.3 `instance_middleware` composition: a retry-exhausted instance
  saved as `in_flight` re-runs on resume.
- §10.6 Retry on resume: `attempt_index` resets to 0, and the retry
  budget restarts fresh.
- §10.7 Per-instance resume: the instances that completed before the
  failure are skipped.

**What passes:**

- The first run raises `provider_unavailable` from `process`, the
  exhausted error's own category (conformance-adapter §5.8), after the
  work body runs five times: once each for instances 0 and 1, and three
  times for instance 2.
- Saved record's instances 0 and 1 are `completed` with results 10 and
  20, and instance 2 is `in_flight` (the failure did NOT record a
  `completed` accumulator entry).
- Resume re-runs instance 2 starting at attempt 0; instance 2 succeeds
  on resume's first attempt (fresh retry budget, different mock).
- Final state reflects all instances succeeding.

**What fails:**

- The work body runs three times in the first run rather than five: the
  failure was not retried.
- Instance 2's `attempt_index` on resume start is 3 (or any non-zero
  value), which would mean the retry budget persisted across resume,
  contradicting §10.6.
- Resume re-runs instance 0 or 1, which would mean instance 2's retry
  exhaustion invalidated their completed status.
- The first run's error reads as `node_exception` rather than
  `provider_unavailable`.

**Notes:**

- The collect-mode counterpart, where a failed instance's error entry is
  saved as a `completed` contribution and rolls forward on resume
  (§10.11.2), is fixture 052, which uses no instance middleware. No
  fixture combines instance middleware with collect mode and resume.
  Fixture 051 covers a `fail_fast` resume whose siblings were cancelled
  or never started.
- The instance retry is written in the middleware-entry form that fixture
  001's header defines, with a zero deterministic backoff so the run does
  not wait between attempts. The spec doesn't mandate the retry
  middleware's parameter names; the harness adapts them to its
  implementation while preserving the behavioral contract.
