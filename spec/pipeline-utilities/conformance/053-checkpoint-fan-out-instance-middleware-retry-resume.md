# 053 — Checkpoint Fan-Out Instance-Middleware Retry Resume

Verifies §10.11.3's composition of per-instance resume with retry
middleware applied at the instance level. A retry-exhausted instance
saved as `in_flight` re-runs on resume with a fresh retry budget
(`attempt_index` reset to 0 per §10.6).

**Spec sections exercised:**

- §10.11.3 `instance_middleware` composition — retry-exhausted
  instances saved as `in_flight` re-run on resume.
- §10.6 Retry on resume — `attempt_index` resets to 0; retry budget
  restarts fresh.
- §10.7 Per-instance resume — completed-before-failure instance
  skipped.
- §9.7 Instance middleware — retry wraps the whole instance subgraph
  invocation as a unit.

**What passes:**

- Saved record's instance 1 is `in_flight` (retry-exhausted failure did
  NOT record a `completed` accumulator entry — the wrapped failure
  prevented it).
- Resume re-runs instance 1 starting at attempt 0; instance 1 succeeds
  on resume's first attempt (fresh retry budget, different mock).
- Final state reflects all instances succeeding.

**What fails:**

- Instance 1's `attempt_index` on resume start is 1 or 3 (or any
  non-zero value) — would mean retry budget persisted across resume,
  contradicting §10.6.
- Resume re-runs instance 0 — would mean the retry-exhaustion of
  instance 1 invalidated instance 0's completed status.
- Instance 1 fails on resume's first attempt and runs further retries
  — acceptable depending on the mock injection, but the fixture's mock
  is constructed so resume succeeds on attempt 0.

**Notes:**

- The complementary case (retry-exhausted-in-collect-mode produces an
  error entry that IS saved as a `completed` contribution) is exercised
  by fixture 052 in spirit — the `instance_middleware` retry vs. raw
  failure distinction doesn't change the §10.11.2 collect-mode rule.
  Adding a dedicated fixture for retry+collect+resume is deferred until
  signal warrants.
- The `retry: {max_attempts: 3}` configuration is illustrative; the
  spec doesn't mandate the retry middleware's parameter names. The
  harness adapts to its implementation's retry-middleware ergonomics
  while preserving the behavioral contract.
