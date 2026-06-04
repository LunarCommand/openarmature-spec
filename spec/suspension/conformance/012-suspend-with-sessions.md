# 012 — Suspend with sessions

When a session is bound to the invocation, the session SHOULD save at
suspend time alongside the paused-invocation record. A fresh worker
resuming the suspension sees consistent session state.

**Spec sections exercised:**

- §8.6 — sessions composition: session saves at suspend; atomic-
  suspend rule (this fixture exercises the success path; the
  `suspension_persistence_failed` failure path is covered by §9 error
  category; future fixture coverage may exercise the atomic-rollback
  case).

**What passes:**

- After the initial suspend, the SessionStore has a record under
  `session_id = "session-suspend-1"` carrying the pre-suspend session
  state (`session_counter: 5`).
- The resume invoke loads the saved session state alongside the
  paused-invocation record; the post-resume node sees consistent state
  and completes normally.
- After resume completes, the SessionStore has the updated final
  state.

**What fails:**

- No session record exists after the initial suspend — would mean the
  session save did not fire at suspend time (would leave a fresh
  worker without the session context needed to resume).
- The resume sees stale session state — would mean the
  paused-invocation record and the session record diverged, breaking
  the atomic-suspend rule.
