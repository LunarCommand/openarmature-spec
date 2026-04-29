# 009 — Retry Middleware: Non-Retryable Passthrough

Verifies the §6.1 default classifier correctly classifies non-transient exceptions as terminal:
when a node fails with `provider_authentication` (an explicit non-transient category), retry
middleware does NOT retry — the exception propagates immediately.

The harness's `flaky_node` exposes a call counter so the assertion "retry middleware did not loop"
is testable: `flaky_call_count` MUST be 1 even though `max_attempts` is 5.

**Spec sections exercised:**

- §6.1 Default transient classifier — non-transient categories return false.
- §6.1 Behavior — `if not classifier(exc, state)` path raises immediately.

**What passes:**

- Engine raises `node_exception` carrying the original `bad key` exception.
- The flaky node's call counter is exactly 1 (no retries despite `max_attempts: 5`).

**What fails:**

- Retry retries on `provider_authentication` (default classifier wrongly classifies it as
  transient).
- Retry consults `state` and decides to retry (the default classifier MUST ignore `state`).
- Call counter > 1 (retry loop ran when it shouldn't).
