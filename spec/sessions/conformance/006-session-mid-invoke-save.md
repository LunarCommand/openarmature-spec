# 006 — Explicit Mid-Invoke Save

Verifies §6.2 explicit mid-invoke save: a node MAY commit current session-projected state to the
store mid-invocation. Such a save survives a subsequent crash within the same invocation that
prevents auto-save from running.

**Spec sections exercised:**

- §6.2 Explicit mid-invoke save — a node-side API commits the current session-projected state
  before END.
- §6.1 Auto-save — does NOT run when the invocation errors before END; the mid-invoke save is the
  only commit that occurs.

**Cases:**

1. `mid_invoke_save_persists_partial_state_on_crash` — A → B → C graph; B saves explicitly; C
   raises. The invocation errors before END. The store contains the partial state from B's save.

**What passes:**

- After the failed invocation, `load(session_id)` returns a record with `{step: "B"}`.
- The engine did NOT auto-save at END (the invocation never reached END).
- A's update is reflected in B's pre-state but is overwritten by B's `update_pure`, so the saved
  state is B's.

**What fails:**

- The mid-invoke save was rolled back when C raised (the spec requires committed mid-invoke saves
  to survive subsequent errors).
- The auto-save ran despite the error (the spec scopes auto-save to successful END).
- The stored state reflects A's update only (B's `update_pure` did not merge before its save).
