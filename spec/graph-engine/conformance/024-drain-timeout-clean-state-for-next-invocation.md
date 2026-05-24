# 024 — Drain Timeout Clean State For Next Invocation

The load-bearing correctness fixture for the §6 Drain "MUST NOT leak"
requirement: workers MUST be cancelled such that the compiled graph
remains usable for subsequent invocations. Two invocations on the same
compiled graph; the first drains with a too-short timeout, the second
drains cleanly.

**Spec sections exercised:**

- §6 Drain — partial delivery state from one drain MUST NOT leak into
  the next invocation.
- §6 Drain — workers MUST be cancelled or otherwise terminated such
  that the compiled graph remains usable.
- §6 Drain — drain summary semantics across both timed-out and
  clean-completion paths.

**What passes:**

- Invocation 1 drains within its 50ms timeout; summary reports
  `timeout_reached: true` and a non-zero `undelivered_count_min`.
- Invocation 2 runs cleanly; drain returns with all 4 events delivered
  and `{timeout_reached: false, undelivered_count: 0}`.
- The observer's second-invocation event list matches expectations
  exactly — no leftover events from invocation 1's undelivered queue,
  no missing events from invocation 2's actual run.

**What fails:**

- Invocation 2 fails to drain (deadlock, exception, hang) — would mean
  the cancelled worker from invocation 1 left the queue in an unusable
  state.
- Invocation 2's `timeline_obs` receives events from invocation 1's
  undelivered queue — would mean cross-invocation leak.
- Invocation 2's `timeline_obs` is missing events — would mean the
  worker state was reset incorrectly.

**Notes:**

- The fixture's correctness is what makes drain-with-timeout safe to
  use in long-running processes (a CLI that runs many invocations,
  each draining with a different timeout). The drain summary is a
  *report*, not a *state mutation*; what one drain failed to deliver
  has no bearing on what the next invocation can deliver.
- New harness primitive: `observers[].sleep_ms_per_event` supports a
  `{first_invocation, subsequent_invocations}` form so a single
  observer can behave differently across the two drains in the same
  fixture.
- New harness primitive: `invocations:` (plural) — a list of
  invocation specs with per-invocation `initial_state`, `drain`, and
  `expected` blocks. Distinct from the single-invocation `invoke:`
  primitive used by fixtures 022 and 023.
