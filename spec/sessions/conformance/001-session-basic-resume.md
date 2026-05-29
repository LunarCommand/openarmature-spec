# 001 — Basic Session Resume

Verifies the core sessions contract (§3 identity scoping, §6.1 auto-save): a `session_id` supplied
at `invoke()` causes the engine to save the final state to the registered `SessionStore` at END,
and a subsequent invoke under the same `session_id` to load that saved state and merge it into the
initial state before the graph runs.

**Spec sections exercised:**

- §3 Identity scoping — `session_id` supplied at invoke; engine loads on entry, saves on exit.
- §6.1 Auto-save — with a store registered and `auto_save` defaulting to true, the engine saves
  the final state at END and loads any existing record at entry.
- §4.1 Full-state sessions — the invoke `State` IS the session state (no projection).

**Cases:**

1. `second_invoke_loads_first_invoke_state` — two invokes under `session_id="s1"`. Invoke #1 starts
   from an empty store and saves `history=["x"]`. Invoke #2 loads that record, and the `append`
   reducer merges the node's `["x"]` onto the loaded `["x"]` → `["x","x"]`.

**What passes:**

- Invoke #1 saves a record under `s1` containing `history=["x"]`.
- Invoke #2's pre-execution state reflects the loaded `history=["x"]` (not the default `[]`).
- Invoke #2 ends with `history=["x","x"]` and saves it (overwriting invoke #1's record).

**What fails:**

- Invoke #2 starts from the default empty state (the saved record was not loaded).
- The engine does not save at END (the record is lost between invokes).
- Loaded state replaces rather than merges (final `["x"]` instead of `["x","x"]`).
