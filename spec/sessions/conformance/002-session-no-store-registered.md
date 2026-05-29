# 002 — Session ID Without a Registered Store

Verifies that supplying a `session_id` at `invoke()` without a registered `SessionStore` is a
no-op for persistence: the invocation runs normally with the caller-supplied initial state, and
no load or save is attempted.

**Spec sections exercised:**

- §3 Identity scoping — `session_id` may be supplied independently of whether a store is
  registered; the engine does not require one to interpret the id.
- §6.1 Auto-save — load and save are conditioned on a registered `SessionStore`; with none, both
  paths MUST be skipped.

**Cases:**

1. `session_id_without_store_is_inert_for_persistence` — single-node graph, no store registered,
   `session_id` supplied. The graph completes normally and the engine never attempts a store
   operation.

**What passes:**

- The graph runs to END with the supplied initial state.
- No load is attempted.
- No save is attempted.

**What fails:**

- The engine raises because no `SessionStore` is registered (presence of `session_id` MUST NOT
  imply a registered store is required).
- The engine attempts a store call against a non-existent backend.
