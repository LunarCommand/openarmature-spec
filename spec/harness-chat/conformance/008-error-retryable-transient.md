# 008 — Retryable transient error mapping (§10.2)

A `provider_unavailable` error (per llm-provider §7) during invocation
routes through harness §7.2 (retryable-transient bucket) to a
`ChatTurnOutcome.errored` carrying a system-shaped reply. §10.2 gives
the reply text as a template that implementations MAY customize, so the
fixture asserts the reply's role and not its text.

The session state is preserved through the transient error (sessions §6
save semantics + the session-not-corrupted post-condition) so a retry can
proceed against the same session.

**Spec sections exercised:**

- harness-chat §10.2 — retryable-transient error mapping
- harness §7.2 — retryable-transient error bucket
- llm-provider §7 — `provider_unavailable` category

**What passes:**

- `send()` returns `ChatTurnOutcome.errored`.
- `.error_bucket` is `retryable_transient`.
- `.reply` is a `role: system` message.
- Session state is preserved (retry against the same session is valid).

**What fails:**

- `.error_bucket` is `session_terminating` or `user_correctable`. That
  would mean the provider_unavailable → §7.2 routing is broken.
- Session state is corrupted post-error — would mean the harness isn't
  honoring the retryable-transient bucket's "retry should be safe"
  semantics.
