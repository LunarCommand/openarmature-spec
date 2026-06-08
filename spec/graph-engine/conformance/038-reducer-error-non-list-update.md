# 038 — `ReducerError` on `bounded_append` non-list update

Verifies graph-engine §4's `ReducerError` runtime category. A list-typed reducer
(`bounded_append` in this case) MUST raise `ReducerError` at merge time when the update is
not a list — paralleling the same strictness the existing `append`, `concat_flatten`, and
`merge_all` reducers enforce.

**Spec sections exercised:**

- graph-engine §4 — `reducer_error` runtime error category.
- graph-engine §2 — `bounded_append` semantics ("Both `prior` and `update` MUST be lists;
  violations raise `ReducerError`").

**Cases:**

1. `bounded_append_non_list_update_raises_reducer_error` — Field declared with
   `bounded_append(max_len=3)`. Node returns a string update where a list is required;
   `ReducerError` surfaces at merge time.

**What passes:**

- The error surfaces as category `reducer_error`, attributed to the offending node `x`.
- The reducer name and offending field name are surfaced in the error (per the §4
  bullet on `ReducerError`).

**What fails:**

- The error is `reducer_configuration_invalid` (this is a runtime contract violation, not a
  configuration-time parameter issue — the spec distinguishes the two).
- The reducer silently coerces the string to a 1-element list — the spec mandates strict
  rejection, parallel to how `append` / `concat_flatten` / `merge_all` reject non-list
  inputs.
- No error is raised (the engine silently accepts the malformed update).
