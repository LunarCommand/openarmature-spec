# 030 — drain_events_for Timeout

When the deliver loop has not caught up to the snapshotted set by the
timeout, `drain_events_for` MUST return within the timeout with a
summary reporting `timeout_reached == true` and a non-zero
`undelivered_count`. Crucially — and this is the load-bearing
difference from the process-wide `drain` — workers MUST NOT be
cancelled on per-invocation drain timeout. The graph remains active
and subsequent invocations MUST run cleanly.

**Spec sections exercised:**

- §6 *Per-invocation drain* — the operation MUST return no later than
  `timeout` seconds after the call begins.
- §6 *Per-invocation drain* — any events still queued or in-flight
  when the timeout is reached are reported as `undelivered`.
- §6 *Per-invocation drain* — workers MUST NOT be cancelled by
  per-invocation drain timeout (load-bearing divergence from
  `drain`'s shutdown-cancel rule).
- §6 *Per-invocation drain* — the deliver loop continues processing
  the queue after a per-invocation drain times out, because the
  graph remains active.

**What passes:**

- The drain summary on the first invocation has `timeout_reached: true`
  and `undelivered_count_min: 4` (most pre-drain events were still
  in-flight when the 50ms timeout fired against the 300ms-per-event
  observer).
- The first invocation reaches END and returns final state cleanly.
- The second invocation runs to completion with no errors — the
  deliver loop is still processing the queue after the first
  invocation's drain timeout.

**What fails:**

- The drain does not return within ~50ms — would mean the hard
  deadline isn't being honored.
- The drain summary has `timeout_reached: false` — would mean the
  drain didn't recognize the timeout fired.
- The drain summary has `undelivered_count: 0` — would mean events
  were dropped or counted as delivered when they weren't.
- The second invocation fails to run or hangs — would mean workers
  were cancelled by the per-invocation drain timeout (the wrong
  semantic; this is what process-wide `drain` does, not
  `drain_events_for`).

**Notes:**

- The load-bearing test is the second invocation succeeding. That's
  what distinguishes per-invocation drain from process-wide drain:
  the graph remains active after a per-invocation timeout, so
  subsequent invocations must work without rebuilding the compiled
  graph or restarting workers.
- This fixture exists in part to lock down the worker-cancellation
  divergence from `drain` — without explicit conformance coverage, a
  naive implementation could share the worker-cancellation code path
  between the two primitives and silently break the per-invocation
  contract.
