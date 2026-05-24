# 049 — Checkpoint Fan-Out Per-Instance Resume Append Reducer

The load-bearing correctness fixture for §10.11.1's append-reducer rule.
A best-effort "may double-contribute" model would cause double-append on
resume; per-instance resume's `completed` status is a correctness
guarantee that prevents this. This fixture is the negative-space proof:
if completed instances were re-run, the final `results` list would have
duplicate entries.

**Spec sections exercised:**

- §10.11.1 Reducer interaction — append reducer's "exactly one
  accumulator entry per instance" correctness guarantee.
- §10.7 Per-instance resume — `completed` instances skip on resume.
- §10.11 `fan_out_progress.result` field carries the durable
  accumulator entry.

**What passes:**

- Saved record's `fan_out_progress` for the process node has instances
  0 and 1 as `completed` with `result` populated (`10` and `20`).
- Resume skips instances 0 and 1 (no `started` events).
- Final `results` list is `[10, 20, 30, 40]` — exactly 4 entries.

**What fails:**

- Final `results` is `[10, 20, 10, 20, 30, 40]` or similar (length 5+
  with duplicates) — would mean completed instances re-ran and
  double-merged through the reducer. This is the failure mode the
  §10.11.1 contract exists to prevent.
- Final `results` is `[30, 40]` only — would mean the saved
  accumulator entries were not preserved across resume.
- Resume executes instances 0 or 1 — would mean the `completed` state
  is being treated as `in_flight` or `not_started`.

**Notes:**

- Distinct from 048 in stress level: 048 verifies the general
  per-instance-resume mechanism; 049 specifically stresses the
  reducer-interaction invariant that motivates the `completed`-as-
  correctness-guarantee framing.
- `last_write_wins` and `merge` reducers have similar but weaker
  failure modes (redundant but idempotent under §5 determinism); append
  is the case where double-merging is *observably wrong*, not just
  wasteful.
