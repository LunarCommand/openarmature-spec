# 022 — Drain Timeout Elapses With Undelivered

Foundational fixture for §6 Drain's bounded-wait contract. A graph runs
with a deliberately slow observer; drain is called with a timeout
shorter than the observer can finish; the timeout fires and the drain
summary reports the unfinished work.

**Spec sections exercised:**

- §6 Drain — optional timeout parameter; hard deadline is non-
  negotiable; summary reports `undelivered_count` and
  `timeout_reached`.
- §6 Drain — graph state remains usable for subsequent invocations
  (this fixture verifies the assertion holds in isolation; fixture
  024 verifies it across an actual second invocation).

**What passes:**

- Drain returns within the configured 100ms timeout window (with
  reasonable scheduler slack).
- Drain summary's `timeout_reached` is `true`.
- Drain summary's `undelivered_count` is ≥ 4 (the per-event sleep is
  200ms; the timeout is 100ms, so at most 0-1 events fully deliver).
- The compiled graph remains in a usable state (no leaked
  cancellation state, queue clean for next invocation).

**What fails:**

- Drain blocks past the timeout — would mean the hard deadline is not
  being honored.
- Drain summary's `timeout_reached` is `false` — would mean the
  implementation isn't surfacing that the timeout fired.
- Drain summary's `undelivered_count` is 0 — would mean either all
  events delivered (impossible given the 200ms × 6 = 1200ms total work
  vs 100ms timeout) or the count is not being computed correctly.
- The compiled graph errors on a subsequent invocation — would mean
  the cancelled worker left undefined state.

**Notes:**

- New harness primitives: `observers[].sleep_ms_per_event` (the slow-
  observer directive), `invoke.drain.timeout_seconds` (drain timeout
  parameter), `expected.drain_summary.{timeout_reached,
  undelivered_count_min}` (summary assertions), and invariants
  `drain_returned_within_timeout` and `graph_state_intact_after_timeout`.
- The `undelivered_count_min` (rather than exact count) accommodates
  implementation variation in worker scheduling. The exact count
  depends on how many events the worker started before the timeout
  fired, which varies with the host language's task scheduler.
