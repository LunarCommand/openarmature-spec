# 003 — Reducer: last_write_wins

Verifies the default scalar reducer: the second write to a scalar field replaces the first.

**Spec sections exercised:**
- §2 Reducer — "The default reducer is *last-write-wins* (the new value replaces the old)."

**What passes:**
- Final `value` is `"second"`.

**What fails:**
- Final `value` is `"first"` (reducer ignored the second write).
- Any other merge behavior.
