# 011 — Middleware Determinism

Verifies §7: middleware that is deterministic in its inputs preserves graph-engine §5
determinism end-to-end. With the retry middleware's random jitter swapped for a deterministic
zero-second backoff, two runs against an identical mocked-failure-then-success scenario produce
identical final state AND identical observer event sequences (including per-attempt events with
`attempt_index`).

**Spec sections exercised:**

- §7 Determinism — deterministic-in-inputs middleware preserves graph-engine §5 guarantees.
- graph-engine §6 Determinism rule — observer event sequence is identical across runs given the
  same inputs and registered observers; this rule extends to middleware-dispatched events.

**What passes:**

- Both runs produce the same `final_state == {v: 100, trace: ["target"]}`.
- Both runs produce the same 6-event observer sequence: a `started` and a `completed` event for
  each of `attempt_index` 0, 1, 2.
- The `completed` events of attempts 0 and 1 have `error.category == node_exception`;
  attempt 2's `completed` event has `post_state` populated.

**What fails:**

- Final state differs across runs (something nondeterministic crept in).
- Observer event count or order differs across runs.
- `attempt_index` values differ between runs (e.g., one run does 2 retries, another does 3).
