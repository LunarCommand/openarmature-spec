# 007 — Session-terminating error mapping (§10.1)

A `session_load_failed` error (per sessions §10) at the harness's session-
load step routes through harness §7.1 (session-terminating bucket) to a
`ChatTurnOutcome.errored` carrying a system-shaped reply. §10.1 gives
the reply text as a template that implementations MAY customize, so the
fixture asserts the reply's role and not its text.

**Spec sections exercised:**

- harness-chat §10.1 — session-terminating error mapping
- harness §7.1 — session-terminating error bucket
- sessions §10 — `session_load_failed` category

**What passes:**

- `send()` returns `ChatTurnOutcome.errored`.
- `.error_bucket` is `session_terminating`.
- `.reply` is a `role: system` message.
- The graph body is NOT invoked (the error surfaces before any node body
  runs).

**What fails:**

- `send()` returns `completed` or `suspended` despite the load failure —
  would mean the harness isn't classifying the error correctly.
- `.error_bucket` is a different bucket. That would mean the
  session_load_failed → §7.1 routing is broken.
- The reply has the wrong role (e.g., assistant) — would mean §10.1's
  system-shaped reply contract is broken.
