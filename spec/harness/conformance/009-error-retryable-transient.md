# 009 — Retryable transient error classification (§7.2)

`provider_unavailable` (llm-provider §7) is classified by the harness
as retryable_transient per §7.2. The harness surfaces the bucket so
callers can decide whether to retry; the spec doesn't mandate
auto-retry behavior (per-runtime).

**Spec sections exercised:**

- harness §7.2 — retryable transient error bucket
- llm-provider §7 — `provider_unavailable` error category

**What passes:**

- Invoke errors with `error.category == provider_unavailable`.
- Harness classifies into the retryable_transient bucket.
- Outbound is an `error_response` carrying the category and the bucket.

**What fails:**

- Bucket classified as terminating — would mean the harness can't
  distinguish retryable failures from session-corruption failures.
- Outbound lacks the bucket. Callers couldn't make a retry decision
  without parsing the error category themselves.
