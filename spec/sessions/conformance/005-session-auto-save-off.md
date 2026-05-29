# 005 — Auto-Save Opt-Out

Verifies §6.3: with `auto_save=False` on the store registration, the engine MUST NOT save the
final state at invoke exit even after END is reached.

**Spec sections exercised:**

- §6.3 Opt-out from auto-save — `auto_save=False` suppresses the engine's automatic save at END.
- §6.2 Explicit mid-invoke save — implied as the only remaining persistence path under opt-out
  (this fixture does not exercise it; see fixture 006).

**Cases:**

1. `auto_save_off_skips_save_at_end` — single-node graph; store registered with
   `auto_save=False`; `session_id` supplied. The graph completes normally; the store contains
   no record for that `session_id` after the invocation.

**What passes:**

- The graph runs to END.
- The engine does not call `save()` at exit.
- `load(session_id)` after the invocation returns None.

**What fails:**

- The engine saves at END despite `auto_save=False`.
- The opt-out is interpreted only as "don't load" rather than "don't save."
