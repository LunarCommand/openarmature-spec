# 007 — Retry Middleware: Success on Second Attempt

Verifies the basic retry happy path: a node that fails once with a transient exception and then
succeeds. The retry middleware catches the failure, retries, and the operation completes — the
caller sees one final success.

The harness's `flaky` node accepts a `failure_sequence` and a `success_update`; the deterministic
backoff (`seconds: 0`) swaps out the spec'd jittered exponential backoff so tests are fast and
reproducible.

**Spec sections exercised:**

- §6.1 Retry behavior — catch transient, sleep (deterministic 0s here), retry.
- §6.1 Default transient classifier — `provider_rate_limit` is in the transient set.
- §6.1 Backoff override — deterministic backoff for testing.

**What passes:**

- Final state is the `success_update`: `{v: 42, trace: ["target"]}`.
- `execution_order` shows `target` once (one composite "successful execution" from the engine's
  perspective, even though there were 2 attempts).
- The retry middleware is exercised — the harness MAY assert internal state if it wants, but the
  externally observable outcome is what matters here. Per-attempt observer events are exercised
  in fixture 015.

**What fails:**

- The first transient exception propagates without retry (default classifier didn't classify
  `provider_rate_limit` as transient).
- Retry exhausts when it shouldn't (max_attempts logic incorrect).
- Final state is missing the `success_update` (retry didn't actually re-run the node).
