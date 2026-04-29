# 008 — Retry Middleware: Exhausted

Verifies retry exhausts cleanly: when `max_attempts` is reached and the final attempt also fails,
the retry middleware lets the final exception propagate to the engine, which surfaces it as a
graph-engine §4 `node_exception` with `recoverable_state` populated.

**Spec sections exercised:**

- §6.1 Retry behavior — `attempt + 1 >= max_attempts` exit condition.
- graph-engine §4 — `node_exception` carries the final attempt's exception as cause and the
  pre-merge state as `recoverable_state`.

**What passes:**

- Engine raises `node_exception` after the third failure.
- Error message matches the third (final) attempt's exception (`"throttle 3"`).
- `recoverable_state` is the pre-merge state at node entry (`{v: 5, trace: []}`).

**What fails:**

- Retry continues past `max_attempts`.
- The first attempt's exception (rather than the final attempt's) propagates.
- Recoverable state is post-merge (no merge happened — every attempt raised).
