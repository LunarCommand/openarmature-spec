# 025 — Drain No Timeout Waits For All

Regression coverage for the v0.3.0 drain contract under the new
optional-timeout API. When drain is called without a timeout parameter,
its behavior MUST be identical to the pre-v0.19.0 behavior — wait until
every event delivers, no truncation. The summary shape is preserved
across timed and untimed paths.

**Spec sections exercised:**

- §6 Drain — backward compatibility: drain without timeout behaves as
  in v0.3.0.
- §6 Drain — drain MUST still return a summary even without a timeout;
  in that case `undelivered_count == 0` and `timeout_reached == false`.
- §6 Drain — consistent summary shape regardless of whether the caller
  supplied a timeout.

**What passes:**

- Drain blocks until all 6 events deliver (~300ms with the 50ms-per-
  event observer pacing).
- Drain summary has `timeout_reached: false` and `undelivered_count: 0`.
- All 6 observer events deliver to `paced_obs` in order.

**What fails:**

- Drain returns before all events deliver — would mean the no-timeout
  path is incorrectly truncating.
- Drain summary is `null` or missing — would mean the new "MUST still
  return a summary" rule isn't being honored on the untimed path.
- `undelivered_count` is non-zero — would mean events were dropped
  despite no timeout being supplied.

**Notes:**

- This fixture catches the implementation regression of returning the
  old (no-summary) result type when no timeout is supplied. The
  consistent-shape requirement is a callable-contract simplification:
  callers don't branch on "did I supply a timeout?" to know whether
  to expect a summary.
- The `drain: {}` form (empty mapping) is the harness equivalent of
  calling drain with no arguments. Distinct from `drain: null` (which
  would mean "don't call drain at all") and from `drain: {timeout_seconds: null}`
  (which is "explicit no-timeout" — semantically equivalent to `drain: {}`).
