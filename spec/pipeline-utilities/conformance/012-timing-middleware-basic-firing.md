# 012 — Timing Middleware: Basic Firing

Verifies the §6.2 timing middleware happy path: per-node registration, the wrapped node runs
successfully, the `on_complete` callback fires once with a record carrying the configured
`node_name`, the elapsed `duration_ms` (deterministic via the clock stub), `outcome ==
"success"`, and `exception_category == null`.

The harness's deterministic-clock stub advances 5 ms per `monotonic()` call. The timing
middleware reads monotonic twice (entry and after `next` returns), so `duration_ms == 5`.

**Spec sections exercised:**

- §6.2 Timing record shape — node_name, duration_ms, outcome, exception_category.
- §6.2 Behavior — `on_complete` fires once per dispatch.
- §6.2 Monotonic clock requirement — the deterministic-clock stub stands in for monotonic.
- §6.2 Per-node node-name capture — user supplies node_name at registration.

**What passes:**

- One record captured.
- `node_name == "worker"`.
- `duration_ms == 5` (exactly one clock tick under the deterministic stub).
- `outcome == "success"`.
- `exception_category == null`.

**What fails:**

- Record not captured (on_complete never fires).
- `node_name` is `null` or wrong (binding lost between registration and call).
- `duration_ms` is 0 (clock not consulted) or negative (wall-clock used instead of monotonic).
- `outcome == "exception"` despite the node succeeding.
