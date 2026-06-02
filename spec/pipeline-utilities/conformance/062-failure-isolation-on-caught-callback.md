# 062 — Failure-isolation middleware: `on_caught` callback fires

Verifies §6.3's optional `on_caught` async callback. When supplied, `on_caught(exc)` MUST fire
when the middleware catches an exception, alongside the framework-emitted observer event and
the degraded return.

**Spec sections exercised:**

- §6.3 — `on_caught` field; lets consumers pump caught exceptions to caller-specific telemetry
  beyond the default observer event.

**Cases:**

1. `on_caught_callback_invoked_with_exception` — A node wrapped with `FailureIsolationMiddleware`
   whose `on_caught` is a recording callback (captures the exception into a state field via a
   side channel for assertion). The node raises a `provider_unavailable` error; the middleware
   catches and returns the degraded update. Asserts:
   - The `on_caught` callback fires exactly once during the catch.
   - The callback receives the original caught exception (matching category + message).
   - The framework-emitted failure-isolation event still emits per the §6.3 contract (the
     callback augments rather than replaces the default event).
   - The degraded return reaches the engine.

**What passes:**

- `on_caught` fires exactly once per catch.
- The exception passed to `on_caught` matches the raised exception (category + message
  preserved).
- The framework-emitted event still emits — `on_caught` is an OPTIONAL additional hook, not a
  replacement.
- The degraded update still reaches the engine.

**What fails:**

- `on_caught` is never invoked despite being supplied — middleware did not honor the optional
  hook.
- `on_caught` fires multiple times for a single catch — re-entry bug.
- The framework-emitted event is suppressed when `on_caught` is supplied — `on_caught` is
  additive, not replacing.
- An exception raised inside `on_caught` propagates outside the middleware in a way that
  prevents the degraded return — `on_caught`'s exceptions are outside the scope of this
  fixture but the documented behavior should not lose the degraded path.
