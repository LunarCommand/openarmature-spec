# 005 — Errored outcome handling (§5.2)

The harness categorizes the error per §7 and surfaces it via a
transport-shaped error response. The classification (terminating /
retryable / user-correctable) is included so the caller can decide
appropriate next steps.

**Spec sections exercised:**

- harness §5.2 — errored outcome handling
- harness §7 — error categorization buckets (this fixture exercises
  §7.2 retryable transient via provider_unavailable)

**What passes:**

- Invoke returns errored with `error.category == provider_unavailable`.
- Harness classifies into the retryable_transient bucket per §7.2.
- Outbound shape is "error_response" with category and bucket.

**What fails:**

- Bucket classification is wrong (e.g., terminating or
  user_correctable) — would mean §7's classification logic is
  incorrect.
- Outbound shape doesn't include the bucket — would mean callers
  can't make retry decisions.
