# 049 — Queryable observer lifecycle: explicit drop required

Verifies §9.4 *Lifecycle* — an accumulating queryable observer that survives across multiple
invocations accumulates buckets per `invocation_id` until explicitly dropped. The framework
MUST NOT auto-drop on the invocation's completion signal (would race against end-of-invocation
reads); the consuming node calls drop explicitly after reading.

**Spec sections exercised:**

- §9.4 *Lifecycle* — auto-drop on completion rejected; explicit `drop(invocation_id)` required
  for accumulating queryable observers; long-lived accumulator memory-pressure caveat.

**Cases:**

1. `accumulator_survives_completion_then_drops_explicitly` — A long-lived accumulating
   observer is constructed once and attached to two sequential invocations. Each invocation's
   final node (a) reads the accumulator's bucket for the current invocation; (b) explicitly
   calls `drop(invocation_id)`. Between the two invocations, the accumulator carries the
   first invocation's bucket (no auto-drop). After invocation 1's final node has run drop,
   the bucket for invocation 1 is gone (the explicit-drop discipline removed it). The
   accumulator is then reused for invocation 2 with a fresh bucket.

   Asserts: invocation 1's read sees a non-empty bucket; invocation 1's drop removes the
   bucket (a subsequent re-read of the same `invocation_id` returns empty / not-present);
   invocation 2's bucket is independent of invocation 1's (no carry-over); auto-drop did NOT
   fire on either invocation's completion signal (the bucket survived completion until
   explicit drop).

**Harness extensions:** the harness MUST support (a) attaching the same observer instance to
two sequential invocations; (b) invoking the observer's `drop(invocation_id)` method from a
node body; (c) capturing the post-drop state of the accumulator for assertion (e.g., "bucket
for X is absent").

**What passes:**

- The first invocation's read captures the accumulated bucket (non-empty by construction).
- The first invocation's explicit drop removes the bucket; a re-read of the same
  `invocation_id` returns empty / not-present.
- The second invocation starts with no carry-over from invocation 1 (a fresh bucket).
- The accumulator's bucket for invocation 1 SURVIVED invocation 1's completion signal up to
  the explicit drop (asserting the no-auto-drop rule).

**What fails:**

- The accumulator auto-drops on the invocation's completion signal — implementation took the
  auto-drop shortcut despite §9.4's MUST NOT rule. The end-of-invocation reader would lose
  access in real use.
- Invocation 2 sees invocation 1's accumulated state — the per-`invocation_id` bucketing
  isn't isolating across invocations.
- The accumulator does not expose a `drop(invocation_id)` method — §9.4 makes this MUST for
  accumulating observers.
