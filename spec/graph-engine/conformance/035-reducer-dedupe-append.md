# 035 — Reducer `dedupe_append(key=None)`

Verifies graph-engine §2's `dedupe_append` reducer (per proposal 0023). The factory returns a
reducer that extends a list with items from the update that are not already present (by key)
in the existing list. First occurrence wins for in-update duplicates.

**Spec sections exercised:**

- graph-engine §2 — `dedupe_append(key=None)` semantics paragraph (proposal 0023).

**Cases:**

1. `dedupe_append_default_key_filters_duplicates_within_update` — `dedupe_append()` with no
   key callable over a list of strings; duplicates within the update + matches against the
   prior list are filtered; order is preserved.
2. `dedupe_append_with_key_callable_filters_by_extracted_field` — `dedupe_append(key=...)`
   over a list of records keyed on `id`; replays the same dedup semantics over the extracted
   key.

Uses the `reducer:` directive's factory form per conformance-adapter §5.2: for factory
reducers taking a `key` callable, the YAML expresses the key as a field-name string; the
adapter constructs the callable as the language-idiomatic accessor for that field.

**What passes:**

- Default-key case: prior preserved; in-update duplicates collapsed to first occurrence;
  match against prior filtered; order preserved (existing-then-novel-update).
- Key-callable case: same semantics applied over the extracted key value.

**What fails:**

- Reducer in-place de-dupes existing items (violates the "no in-place dedup of existing"
  rule).
- Last-occurrence-wins for in-update duplicates (violates the first-occurrence-wins rule).
- Order is not preserved (existing items must appear before update items in the result).
