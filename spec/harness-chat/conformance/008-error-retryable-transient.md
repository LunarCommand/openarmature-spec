# 008 — Retryable transient error mapping (§10.2)

A `provider_unavailable` error (per llm-provider §7) during invocation
routes through harness §7.2 (retryable-transient bucket) to a
`ChatTurnOutcome.errored` carrying a system-shaped reply matching the
§10.2 template ("I had trouble responding. Try again in a moment.").

The session state is preserved through the transient error (sessions §6
save semantics + the session-not-corrupted post-condition) so a retry can
proceed against the same session.

**Spec sections exercised:**

- harness-chat §10.2 — retryable-transient error mapping
- harness §7.2 — retryable-transient error bucket
- llm-provider §7 — `provider_unavailable` category

**What passes:**

- `send()` returns `ChatTurnOutcome.errored`.
- `.error_category` is `"retryable_transient"`.
- `.reply` is a `role: system` message containing the "try again in a
  moment" framing.
- `.error_diagnostic` (when surfaced) is `"provider_unavailable"`.
- Session state is preserved (retry against the same session is valid).

**What fails:**

- `.error_category` is `session_terminating` or `user_correctable` — would
  mean the provider_unavailable → §7.2 routing is broken.
- Session state is corrupted post-error — would mean the harness isn't
  honoring the retryable-transient bucket's "retry should be safe"
  semantics.
