# 022 — Fan-Out Count and Concurrency Modes

Verifies the `count` mode (no `items_field`) and the int-or-callable shape for both `count` and
`concurrency`. Four sub-cases.

The harness exposes named callable factories for use in YAML (literal closures aren't expressible
in YAML):

- `state_field_read` — `lambda state: getattr(state, field)`
- `queue_chunk` — `lambda state: max(1, len(getattr(state, field)) // chunk_size)`

**Spec sections exercised:**

- §9 Configuration — `count` config field; mutual exclusion with `items_field`.
- §9.1 Per-instance projection — count mode (no `item_field`); resolved at fan-out entry.
- §9.2 Concurrent execution — `concurrency` int-or-callable; resolved once at fan-out entry.

**Cases:**

1. `count_literal` — `count: 3`. Three instances run; each starts with subgraph schema defaults
   plus any `inputs` mapping; no `item_field` projection.
2. `count_callable_from_state` — callable reads `state.worker_count` (= 4). Four instances run.
3. `count_callable_computed` — callable computes from `len(state.queue) // 10`, with `max(1, …)`
   floor. State has 35-element queue → 3 instances run.
4. `concurrency_callable_with_items_field` — `items_field` mode with 6 items; concurrency
   callable reads `state.allowed_in_flight` (= 2). All six items processed but at most 2
   concurrent at any moment, asserted via per-instance entry/exit timing markers.

**What passes:**

- Each case's `final_state` matches the expected pattern.
- Case 4: the harness's `max_in_flight` measurement is exactly 2.
- `item_field` is correctly absent in count modes.
- `fan_out_index` values run `0..count-1` on observer events.

**What fails:**

- `count` callable is invoked more than once (it should be resolved exactly once at fan-out
  entry).
- Case 4 has more than 2 instances running concurrently — concurrency wasn't honored.
- A count of 0 raises an error (empty fan-out should be a no-op per §9.1).
