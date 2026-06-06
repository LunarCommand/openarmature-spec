# 009 — User-correctable error mapping (§10.3)

A `provider_invalid_request` error (per llm-provider §7) with a diagnostic
message routes through harness §7.3 (user-correctable bucket) to a
`ChatTurnOutcome.errored` carrying a system-shaped reply that
**incorporates the upstream diagnostic**. The diagnostic must surface in
the reply text so the user can act on it; over-redaction defeats the
user-correctable bucket's purpose per §10.3.

**Spec sections exercised:**

- harness-chat §10.3 — user-correctable error mapping
- harness §7.3 — user-correctable error bucket
- llm-provider §7 — `provider_invalid_request` category

**What passes:**

- `send()` returns `ChatTurnOutcome.errored`.
- `.error_category` is `"user_correctable"`.
- `.reply` is a `role: system` message that includes BOTH the upstream
  diagnostic substring ("context length exceeds maximum") AND the
  user-correctable bucket's "adjust your message" framing.
- `.error_diagnostic` is `"provider_invalid_request"`.

**What fails:**

- `.error_category` is `retryable_transient` — would mean the
  provider_invalid_request → §7.3 routing is broken.
- `.reply` omits the upstream diagnostic substring — would mean §10.3's
  "surface enough diagnostic that the user can act on it" rule is broken
  (over-redaction).
- `.reply` is missing the "adjust your message" framing — would mean the
  user-correctable bucket's call-to-action framing is broken.
