# 010 — User-correctable error classification (§7.3)

`provider_invalid_request` (llm-provider §7) is classified by the
harness as user_correctable per §7.3. The harness surfaces with
diagnostic information so the caller can adjust inputs and retry
explicitly.

**Spec sections exercised:**

- harness §7.3 — user-correctable error bucket
- llm-provider §7 — `provider_invalid_request` error category

**What passes:**

- Invoke errors with `error.category == provider_invalid_request`.
- Harness classifies into the user_correctable bucket.
- Outbound includes a non-empty `diagnostic_message`. §7.3 does not fix
  what the diagnostic information says, so its text is not asserted.

**What fails:**

- Bucket classified as retryable_transient — would mean an
  invalid-input failure could be silently auto-retried (and would
  fail the same way).
- Diagnostic message missing — would mean the caller can't see what
  to fix.
