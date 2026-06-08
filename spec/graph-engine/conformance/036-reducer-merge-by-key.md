# 036 — Reducer `merge_by_key(key)`

Verifies graph-engine §2's `merge_by_key` reducer (per proposal 0023). The factory returns a
reducer for list-of-records fields. Items in the update with a key matching an existing entry
REPLACE that entry in place; items with novel keys are appended at the end in update order.

**Spec sections exercised:**

- graph-engine §2 — `merge_by_key(key)` semantics paragraph (proposal 0023).

**Cases:**

1. `merge_by_key_replace_existing_preserves_position` — All 3 update keys match existing
   entries; each existing entry is replaced in place; the existing order is preserved
   (replacement does NOT reorder).
2. `merge_by_key_append_novel_at_end_in_update_order` — All 3 update keys are novel; the
   3 update items are appended at the end of the prior list in the order they appeared in
   the update.
3. `merge_by_key_mixed_replace_and_append` — Mixed updates: 2 keys match existing (replace
   in place); 2 keys are novel (append at end). Final list: prior entries in original order
   (with replacements applied) + novel entries appended in update order.

**What passes:**

- Replace cases: existing entry position is preserved; the replacement update item takes
  the existing slot.
- Append cases: novel entries appear AFTER all existing entries, in update order.
- Mixed cases: positional behavior holds — existing entries (potentially replaced) come
  first; novel entries come after in update-arrival order.

**What fails:**

- Replacement reorders entries (e.g., moves the replaced entry to the end).
- Novel entries are inserted alongside existing entries rather than appended at the end.
- Novel entries are in any order other than update-arrival order.
- `merge_by_key` is treated as `merge` (dict-shallow-merge) — the spec distinguishes the
  two via the `_by_key` qualifier; `merge_by_key` operates on list-of-records, `merge`
  operates on dict-typed fields.
