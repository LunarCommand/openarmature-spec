# 027 — merge_all reducer

Verifies §2's `merge_all` required built-in reducer. Mirrors `merge`'s strict shape contract
but for the N-mappings shape: `merge_all(prior, update)` folds the sequence of mappings in
`update` into `prior` with shallow last-write-wins per key (consistent with `merge`'s single-dict
semantics). Both arguments strictly required to be mappings/lists; every element of `update`
strictly required to itself be a mapping.

**Spec sections exercised:**

- §2 Reducer entry — required-built-in set includes `merge_all`.
- §2 `merge_all` semantics paragraph — strict list-of-mappings shape, shallow last-write-wins
  per key fold across the N dicts in `update`, empty `update` no-op, empty mappings inside
  `update` contribute zero keys, ReducerError per §4 on non-mapping element.
- §2 Reducer entry — `merge`'s shallow last-write-wins semantics (which `merge_all` extends
  across N mappings).
- §4 Error categories — `reducer_error` raises when the reducer encounters bad input.

**Cases:**

1. `success_folds_mappings_with_last_write_wins` —
   `prior = {seed_key: "seed_value", retained: "from_prior"}`,
   `update_1 = [{a: "1"}, {seed_key: "overwritten_in_x", b: "2"}, {a: "1_wins_over_first"}]`,
   `update_2 = [{b: "y_wins"}, {c: "3"}]` →
   `{seed_key: "overwritten_in_x", retained: "from_prior", a: "1_wins_over_first", b: "y_wins", c: "3"}`.
   Verifies (a) folding across multiple mappings in one update, (b) within-update
   last-write-wins (the third `a` mapping wins over the first), (c) prior keys preserved when
   no writer touches them (`retained`), and (d) cross-write last-write-wins (node y's `b` value
   wins over node x's).
2. `empty_update_is_noop` — `prior = {k: "v"}`, `update = []` → `{k: "v"}`. The reducer returns
   the prior unchanged.
3. `empty_mappings_contribute_zero_keys` — `prior = {prior_key: "prior_value"}`,
   `update = [{}, {}]` → `{prior_key: "prior_value"}`. Empty mappings inside `update` are valid
   and contribute no keys.
4. `non_mapping_element_raises_reducer_error` — `prior = {}`,
   `update = [{k: "1"}, "not_a_mapping"]` → `reducer_error` raised from node `x`. The reducer is
   the gatekeeper for element-shape and MUST surface the offending field and reducer name in
   the error.

**Harness notes:**

- Field type is `dict` (no value constraint) so the reducer is the layer enforcing the
  list-of-mappings shape rather than the typed-state validation layer. Implementations whose
  typed-state validation rejects non-mapping-element updates BEFORE the reducer will catch the
  non-mapping-element case at the state validation layer rather than at the reducer; that
  behavior also satisfies §2's strict contract but does NOT raise `reducer_error` specifically.
  The fixture's permissive `type: dict` ensures the reducer is the layer enforcing the contract.
- Non-list `update` and non-mapping `prior` cases are spec-normative (the reducer MUST raise on
  these per §2) but are typically caught at the state validation layer in strict-typed
  implementations before reaching the reducer. The fixture's non-mapping-element case is the
  one the reducer is GUARANTEED to be the gatekeeper for.

**What passes:**

- Case 1 final state has the cumulative shallow merge with all last-write-wins relations
  resolved correctly (within `update` AND across `update`s).
- Case 2 final state is the prior unchanged.
- Case 3 final state is the prior unchanged (despite non-empty `update` containing two empty
  mappings).
- Case 4 raises `reducer_error` from node `x`.

**What fails:**

- Case 1: prior keys not preserved (`retained` missing), or last-write-wins inverted (`b`
  resolves to `"2"` instead of `"y_wins"`), or `a` resolves to `"1"` instead of
  `"1_wins_over_first"` — fold ordering broken.
- Case 2: error raised on empty update — empty-update no-op semantic broken.
- Case 3: error raised on empty inner mappings — empty mapping semantic broken.
- Case 4: no error raised, or error category is something other than `reducer_error` — reducer
  is silently coercing bad input rather than failing fast.
