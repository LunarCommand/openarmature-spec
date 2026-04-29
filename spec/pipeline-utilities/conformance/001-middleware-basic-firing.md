# 001 — Middleware Basic Firing

Smallest possible test: a single node with one per-node middleware that records what it sees.
Establishes that the implementation actually wires up middleware (the wrapper runs, sees the
input state, sees the returned partial update) before testing any of the more nuanced behaviors
in 002–016.

Also documents the **conformance fixture format** for pipeline-utilities, including the test-only
middleware types (`trace_recorder`, `short_circuit`, `error_recovery`, `error_raiser`,
`state_inspector`) the harness exposes. Subsequent fixtures reuse this format. See the comment
header in the YAML file for the format reference.

**Spec sections exercised:**

- §2 Middleware shape — `(state, next) -> partial_update`.
- §2 Pre-node and post-node phases — pre-phase observes input state; post-phase observes returned
  partial update.
- §3 Per-node middleware registration.

**What passes:**

- The `trace_recorder` middleware is invoked exactly once with the pre-merge state `{v: 0, trace:
  []}`.
- The wrapped node `a` runs and returns `{v: 1, trace: ["a"]}`.
- The recorder captures the partial update on the way back out.
- The engine merges the partial update; `final_state` is `{v: 1, trace: ["a"]}`.

**What fails:**

- Middleware not invoked (engine bypasses the registration).
- Middleware sees a post-merge state instead of pre-merge state.
- The recorder sees a transformed partial update (the engine should have merged, not the
  middleware).
