# 003 — Store Registered, No Session ID Supplied

Verifies that a registered `SessionStore` is dormant unless `session_id` is supplied: omitting
`session_id` MUST cause the engine to skip both load and save, regardless of the registered store.

**Spec sections exercised:**

- §3 Identity scoping — "When `session_id` is omitted, the engine MUST NOT call into the
  `SessionStore` even if one is registered. The session machinery is opt-in per-invoke."

**Cases:**

1. `omitted_session_id_never_touches_store` — single-node graph with an in-memory store
   registered, `session_id` NOT supplied. The graph runs normally and the store is untouched.

**What passes:**

- The graph runs to END with the supplied initial state.
- No load is attempted.
- No save is attempted.
- The store's contents are unchanged after the invocation.

**What fails:**

- The engine implicitly mints a `session_id` and calls into the store (the spec forbids this —
  the caller MUST supply `session_id` for the session machinery to engage).
- The engine attempts a `list()` or similar exploratory call to the store.
