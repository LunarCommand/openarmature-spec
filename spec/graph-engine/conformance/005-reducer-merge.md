# 005 — Reducer: merge

Verifies that the `merge` reducer combines mapping-typed updates with shallow merge semantics: later writes
win on key conflicts; non-conflicting keys from prior state and from all writers are preserved.

**Spec sections exercised:**
- §2 Reducer — `merge` is a required reducer for mapping-typed fields.

**What passes:**
- Final `metadata` contains all four keys: `source` (from initial), `author` (from `a`), `reviewer` (from
  `b`), and `stage == "final"` (last writer wins over `a`'s `"draft"`).

**What fails:**
- Final `metadata` equals the literal update from the last node (`{stage: "final", reviewer: "bob"}`),
  which would indicate `merge` fell back to `last_write_wins`.
- `stage` is `"draft"` instead of `"final"` (conflict resolution ordering reversed).
- Missing `source: "seed"` (initial state discarded).

**Out of scope:**
This fixture verifies shallow merge only. Deep-merge behavior for nested mappings is not specified by this
capability spec.
