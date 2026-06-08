# 034 — Reducer `bounded_append(max_len)`

Verifies graph-engine §2's `bounded_append` reducer (per proposal 0023). The factory returns a
reducer that extends a list with the update's items and truncates from the front (oldest entries
dropped first) when the post-merge length exceeds `max_len`.

**Spec sections exercised:**

- graph-engine §2 — `bounded_append(max_len)` semantics paragraph (proposal 0023).

**Cases:**

1. `bounded_append_basic_truncates_when_concat_exceeds_bound` — Single update of 5 items into
   an empty list with `max_len=3`. Final list is the last 3 items.
2. `bounded_append_multi_step_cumulative_bound_across_merges` — Three nodes each append 2 items
   to a field with `max_len=4`. After each merge the bound is enforced; final list is the last
   4 items across all updates.
3. `bounded_append_update_larger_than_max_len_evicts_prior_entirely` — Single update of 5 items
   into a 2-item prior with `max_len=2`. Prior is fully evicted; final list is the last 2
   items of the update.

**Per-suite directive:**

- `reducer:` value may be a single-key mapping `{<factory_name>: <kwargs>}` for factory
  reducers, in addition to the string form for parameter-less reducers. The adapter
  instantiates the named factory with the kwargs at field-registration time.

**What passes:**

- Final list is the LAST `max_len` items across all merges (front-drop semantics).
- The bound applies to the post-merge length, not to the update's individual size.

**What fails:**

- Truncation from the back (newest dropped) — violates the front-drop cross-impl rule.
- The bound is applied per-update rather than post-merge.
- Prior is preserved when the update alone exceeds `max_len` — should be fully evicted.
