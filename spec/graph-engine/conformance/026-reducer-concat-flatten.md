# 026 — concat_flatten reducer

Verifies §2's `concat_flatten` required built-in reducer. Mirrors `append`'s strict shape
contract but for the two-level list-of-lists case: `concat_flatten(prior, update)` concatenates
`prior` with the one-level flattening of `update`, with both arguments strictly required to be
lists and every element of `update` strictly required to itself be a list.

**Spec sections exercised:**

- §2 Reducer entry — required-built-in set includes `concat_flatten`.
- §2 `concat_flatten` semantics paragraph — strict list-of-lists shape, empty `update` no-op,
  empty sub-lists contribute zero elements, ReducerError per §4 on non-list element.
- §4 Error categories — `reducer_error` raises when the reducer encounters bad input.

**Cases:**

1. `success_concatenates_and_flattens` — `prior = ["a", "b"]`, `update_1 = [["c"], ["d", "e"], []]`,
   `update_2 = [["f"]]` → `["a", "b", "c", "d", "e", "f"]`. Verifies concatenation with prior,
   one-level flatten across update elements, and empty sub-list `[]` contributing zero elements.
2. `empty_update_is_noop` — `prior = ["a"]`, `update = []` → `["a"]`. The reducer returns the
   prior unchanged.
3. `empty_sub_lists_contribute_zero_elements` — `prior = []`, `update = [[], []]` → `[]`. Empty
   sub-lists are valid and contribute no elements (the one-to-many fan-out case where an
   instance produces zero records).
4. `non_list_element_raises_reducer_error` — `prior = []`, `update = [["a"], "not_a_list"]` →
   `reducer_error` raised from node `x`. The reducer is the gatekeeper for element-shape and
   MUST surface the offending field and reducer name in the error.

**Harness notes:**

- This fixture asserts the §2 contract that `concat_flatten` raises `reducer_error` on shape
  violations. The permissive `type: list` (no element constraint) ensures the reducer is the
  layer reached by the bad shape, making the `reducer_error` assertion the right one for the
  non-list-element case.
- A separately constrained field (e.g., a Pydantic field declared `list[list[X]]`) would have
  its typed-state validation reject the bad shape earlier, before the reducer runs — but that's
  a different code path, not an alternative satisfaction of §2. The §2 contract for what the
  reducer does when it sees bad shape is what this fixture asserts.
- Non-list `update` and non-list `prior` cases are spec-normative (§2 says the reducer MUST
  raise on these) but require similar permissive-type setups to exercise at the reducer layer;
  in strict-typed implementations they are typically rejected at the state-validation layer
  for the field carrying the bad value. The fixture's non-list-element case is the one the
  reducer is guaranteed to be the gatekeeper for under a permissive field type.

**What passes:**

- Case 1 final state has the concatenated, flattened result.
- Case 2 final state is the prior unchanged.
- Case 3 final state is empty (despite non-empty `update` containing two empty sub-lists).
- Case 4 raises `reducer_error` from node `x`.

**What fails:**

- Case 1: nesting preserved (`[["c"], ...]`) — flattening didn't happen; reducer is acting like
  `append`.
- Case 2: error raised on empty update — empty-update no-op semantic broken.
- Case 3: error raised on empty sub-lists — empty inner-list semantic broken.
- Case 4: no error raised, or error category is something other than `reducer_error` — reducer
  is silently coercing bad input rather than failing fast.
