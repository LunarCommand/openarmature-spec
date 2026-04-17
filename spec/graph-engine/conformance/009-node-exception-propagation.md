# 009 — Node Exception Propagation

Verifies that when a node raises, execution halts, the exception propagates to the caller, and the state at
the point of failure is recoverable.

**Spec sections exercised:**
- §4 Error semantics — "If a node raises, execution halts and the exception propagates to the caller. The
  partial state at the point of failure MUST be recoverable (exposed on the raised error or via a documented
  accessor)."

**What passes:**
- Node `a` runs to completion, appending `"a"` to `log`.
- Node `b` raises `"boom"`; execution halts.
- Node `c` never runs.
- The raised error (or a documented accessor on it) exposes `{log: ["a"]}` as the recoverable state.
- Observed execution order is `[a, b]` — `b` *was* entered, it just did not complete.

**What fails:**
- Node `c` runs anyway (engine swallowed the exception).
- Recoverable state includes any contribution from `b` (whose update was never returned) or `c` (which never
  ran).
- Error propagates without a recoverable-state accessor.
