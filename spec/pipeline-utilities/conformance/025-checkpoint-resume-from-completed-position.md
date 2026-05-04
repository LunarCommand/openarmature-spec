# 025 — Resume From Completed Position

Verifies §10.4 resume model end-to-end: a graph aborts mid-execution; the saved checkpoint
captures all `completed` events up to (but not including) the failing node; on resume, the
engine restores state from the saved record and continues from the first node whose position
is not in `completed_positions`.

**Spec sections exercised:**

- §10.4 Resume model — `invoke(resume_invocation=...)` loads the prior record, restores
  state, mints a new `invocation_id`, preserves `correlation_id`, and resumes at the first
  not-yet-completed node.
- §10.3 Save granularity — node A's `completed` event saved; node B's `started` fired but no
  `completed` save (failure captured).
- §10.5 Idempotency contract — node A is NOT re-run on resume; mid-node crash on B causes B
  to re-run from its entry on resume.

**Cases:**

1. `abort_in_b_resume_skips_a` — three nodes A → B → C; B raises on first run; resume invoked
   with `resume_invocation=<original id>`; assert A is skipped, B and C run, final state
   matches what an uninterrupted run produces.

**What passes:**

- A's effects are restored (not re-applied) — the saved `state` at resume entry shows
  `a_ran: true`.
- B and C run during the resumed execution.
- A's `started`/`completed` events do NOT fire during the resumed run (it's not re-executed).
- The resumed run has a new `invocation_id`; the `correlation_id` matches the original.

**What fails:**

- Engine re-runs node A on resume (treats `completed_positions` as advisory rather than
  authoritative).
- Resume restarts the whole graph from the entry node.
- The resumed run reuses the original `invocation_id` (per §10.4 step 4 it MUST mint a new
  one).
- `correlation_id` changes on resume (per §10.4 step 3 it MUST be preserved).
