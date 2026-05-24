# 023 — Drain Timeout Not Reached, Fast Observers

The complementary case to fixture 022: a timeout is supplied but does
not fire because the observers finish their work well within the
deadline. Verifies that the summary correctly reports no timeout.

**Spec sections exercised:**

- §6 Drain — when the timeout does NOT fire, `timeout_reached` MUST be
  `false` and `undelivered_count` MUST be `0`.
- §6 Drain — all observer events deliver normally; the timeout is just
  an upper bound, not a forced wait.

**What passes:**

- Drain returns as soon as all events deliver (well before the 5-second
  timeout).
- Drain summary's `timeout_reached` is `false`.
- Drain summary's `undelivered_count` is `0`.
- All 6 observer events (3 nodes × started + completed) deliver to
  `fast_obs`.

**What fails:**

- Drain waits for the full timeout — would mean the implementation is
  treating the timeout as a forced minimum wait, not an upper bound.
- Drain summary's `timeout_reached` is `true` — would mean the flag is
  being set incorrectly.
- `undelivered_count` is non-zero — would mean events were dropped
  despite the timeout not firing.

**Notes:**

- The 5-second timeout is generous enough that even with substantial
  scheduler slack the observers finish well within it. The fixture's
  point is to verify the no-timeout-fired path, not to stress
  scheduling.
- Distinct from fixture 025 (no timeout supplied at all): this fixture
  supplies a timeout that simply doesn't fire. The summary shape is the
  same in both cases.
