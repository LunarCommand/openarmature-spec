# 030 — Checkpoint Not Found

Verifies §10.10's `checkpoint_not_found` error category. The error fires when
`invoke(resume_invocation=X)` is called and `Checkpointer.load(X)` returns `None` —
either because the store is empty or because no record matches the supplied id. The error
is non-transient: retry middleware MUST NOT classify it as recoverable, since the missing
record genuinely does not exist and re-attempting would not help.

**Spec sections exercised:**

- §10.10 Errors — `checkpoint_not_found` canonical runtime category.
- §10.4 step 1 — engine raises `checkpoint_not_found` when `Checkpointer.load` returns
  `None`.
- §10.5 Idempotency contract — non-transient categories are not auto-recovered by retry
  middleware.

**Cases:**

1. `resume_against_empty_checkpointer` — `invoke(resume_invocation="ghost")` against an
   in-memory Checkpointer that has never been populated. Engine raises
   `checkpoint_not_found`.
2. `resume_with_mismatched_id_when_other_records_exist` — checkpointer is populated with
   records from prior unrelated runs; `invoke(resume_invocation="never-existed")` with a
   fabricated id that matches none of them. Engine raises `checkpoint_not_found` — the
   error fires per-id, not "is the store empty?"

**What passes:**

- Both sub-cases raise `checkpoint_not_found`.
- The error is classified non-transient.
- The error surfaces immediately on `invoke()` entry, before any node runs.

**What fails:**

- Engine returns silently and runs the graph from its entry node when no record matches
  (would mask the user's misconfiguration).
- Error category is something other than `checkpoint_not_found` (e.g.,
  `checkpoint_record_invalid` or `node_exception`).
- Error is classified transient and gets retried (would loop indefinitely against an
  empty store).
- The "store has other records" sub-case succeeds because the engine resumed the most
  recent record instead of the requested one (would be a silent data hazard).
