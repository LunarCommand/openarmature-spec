# 054 — Checkpoint Fan-Out Batching Buffered Saves Lost on Crash

Verifies §10.11.4's configurable batching for fan-out internal saves.
A Checkpointer with batching enabled buffers fan-out internal saves and
flushes at configured intervals; a crash with buffered-but-unflushed
saves loses those records. The fixture asserts that the loss is
ACCEPTABLE — the buffered-only-completed instances re-run on resume and
contribute to outer state for the first time, with no double-merge
under the §10.11.1 reducer rules.

**Spec sections exercised:**

- §10.11.4 Configurable batching — flush-every-N semantics; buffered
  saves lost on crash; re-execution acceptable under §10.11.1 rules.
- §10.11.1 Reducer interaction — `append` reducer's exactly-once
  contribution guarantee holds even when batching loss forces
  re-execution.
- §10.7 Per-instance resume — only `completed` (flushed) instances
  skip.

**What passes:**

- Saved record after crash: instances 0-4 are `completed` with results
  preserved (flushed before crash); instances 5-9 are NOT `completed`
  (their saves either buffered-but-unflushed or never fired).
- Resume re-runs instances 5-9; skips instances 0-4.
- Final `results` list has exactly 10 entries, no duplicates — the
  re-executed instances 5-6 contribute for the first time.

**What fails:**

- Saved record has instances 5 or 6 as `completed` — would mean
  batching's buffer was flushed early (acceptable IF the flush
  semantics declare so), OR the implementation isn't actually batching.
- Resume skips instances 5 or 6 — would mean the implementation is
  treating buffered state as `completed`, which violates the
  "buffered ≠ durable" rule in §10.11.4.
- Final `results` has duplicate entries or wrong length — would mean
  the re-executed instances are double-merging, violating §10.11.1.

**Notes:**

- The `checkpointer.kind: in_memory_batched` and
  `fan_out_internal_save_batching.flush_every: 5` are new harness
  primitives introduced by this fixture. The harness implementation
  decides the actual buffer semantics (count-based, time-based, or
  hybrid); the behavioral contract under §10.11.4 is what's asserted.
- `state_one_of: [in_flight, not_started]` accommodates implementation
  variation in how instances mid-execution-at-flush-loss are
  represented on the loaded record. The critical assertion is that
  they're NOT `completed`.
- The `batching_scoped_to_fan_out_internal_saves_only` invariant is
  structural — it cannot be falsified by this fixture alone, but it's
  asserted as documentation of the §10.11.4 contract that batching
  MUST NOT apply to outermost-graph saves, subgraph-internal saves, or
  the fan-out node's own completion save. Other fixtures in the suite
  exercise those save paths under a batched Checkpointer to verify
  they remain synchronous.
