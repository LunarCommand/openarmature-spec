# 008 — Session-terminating error classification (§7.1)

`session_load_failed` (sessions §10) is classified by the harness as
session-terminating per §7.1. The harness surfaces a
"session is broken; intervention required" outbound shape and SHOULD
NOT auto-retry.

**Spec sections exercised:**

- harness §7.1 — session-terminating error bucket
- harness §5.2 — errored outcome handling
- sessions §10 — `session_load_failed` error category

**What passes:**

- Invoke errors with `error.category == session_load_failed`.
- Harness classifies into the session_terminating bucket.
- Outbound includes the bucket + `intervention_required: true` flag.
- NO auto-retry — `harness_auto_retried == false`.

**What fails:**

- Bucket classified as retryable or user-correctable — would mean
  §7.1's "terminating" rule is broken (and auto-retry could damage
  the broken session further).
- Harness auto-retried — violates §7.1's SHOULD NOT auto-retry rule
  (depending on the implementation's SHOULD-strict reading, this
  may be a hard or soft fail).
