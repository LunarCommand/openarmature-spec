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

**Cases:**

1. `resume_sees_consistent_session_state` applies to every adapter. The
   invocation suspends and resumes, and the session record holds the
   final state. These assertions hold whether or not the session saves
   at suspend time.
2. `session_saves_at_suspend_time` is gated on `session_save_at_suspend`
   (fixture 001's note), since §8.6 makes the suspend-time save a
   SHOULD. Once the suspended call returns, the store holds the
   pre-suspend session state.

**What passes:**

- Case 1: the resume invoke continues from the paused-invocation
  record; the post-resume node sees consistent state and completes
  normally.
- Case 1: after resume completes, the SessionStore has the updated final
  state.
- Case 2: after the initial suspend, the SessionStore has a record under
  `session_id = "session-suspend-1"` carrying the pre-suspend session
  state (`session_counter: 5`).

**What fails:**

- Case 1: the resume sees stale session state. That would mean the
  paused-invocation record and the session record diverged, breaking
  the atomic-suspend rule.
- Case 2: no session record exists after the initial suspend. That would
  mean the session save did not fire at suspend time, leaving a fresh
  worker without the session context needed to resume.
