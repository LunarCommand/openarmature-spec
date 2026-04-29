# 014 — Timing and Retry Composition

Verifies the §6.2 "Composition with retry" guidance: ordering of timing and retry produces
fundamentally different observability shapes. Two sub-cases (table-style fixture):

- **`timing_wraps_retry`** — `[timing, retry, node]`. The timing middleware wraps the retry
  middleware. `on_complete` fires ONCE with the elapsed time across all retry attempts. Use this
  for end-to-end latency dashboards ("how long did the user actually wait?").

- **`retry_wraps_timing`** — `[retry, timing, node]`. The retry middleware wraps the timing
  middleware. `on_complete` fires N times (once per attempt) with per-attempt durations and
  outcomes. Use this for per-attempt visibility ("how long did each attempt take? which ones
  failed?").

Both compositions are valid; neither is more correct. The user picks based on what observability
question they're answering.

**Spec sections exercised:**

- §6.2 Composition with retry — the order-dependence semantics.
- §3 Composition order — the user-declared order is honored.

**What passes:**

- `timing_wraps_retry`: exactly one captured record with `outcome == "success"` and
  `exception_category == null`.
- `retry_wraps_timing`: exactly three captured records — two with `outcome == "exception"`,
  `exception_category == "provider_rate_limit"`; one with `outcome == "success"`,
  `exception_category == null`. In input order (failure 1, failure 2, success).

**What fails:**

- `timing_wraps_retry` produces multiple records — timing didn't actually wrap retry as a unit.
- `retry_wraps_timing` produces only one record — retry suppressed the inner timing's per-attempt
  firing.
- Per-attempt records lack `exception_category` — extraction logic missing.
