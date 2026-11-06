# 013 — Timing Middleware: Failure Path

Verifies the §6.2 timing middleware correctly handles the failure case: the wrapped node raises
with a `category` attribute (here `provider_rate_limit`), the timing middleware records
`outcome == "exception"` and `exception_category == "provider_rate_limit"`, then re-raises, so
the invocation raises an error whose category is `provider_rate_limit`.

**Spec sections exercised:**

- §6.2 Behavior — on_complete fires before the exception propagates.
- §6.2 Record `exception_category` — extracted from the exception's `.category` attribute when
  present.
- §6.2 The exception propagates after `on_complete` fires (does not get swallowed by timing).

**What passes:**

- One record captured with `outcome == "exception"` and `exception_category ==
  "provider_rate_limit"`.
- The invocation raises an error whose category is `provider_rate_limit` and whose message is
  `boom`, both read from the node's own error.
- `duration_ms == 5` (deterministic clock).

**What fails:**

- on_complete never fires because the exception preempted it.
- `exception_category` is null despite the exception having a `.category` attribute (extraction
  logic missing).
- The timing middleware swallows the exception (graph completes "successfully" instead of raising).
- `outcome` is `"success"` despite the failure.
