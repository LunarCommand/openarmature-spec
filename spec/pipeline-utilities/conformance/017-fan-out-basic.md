# 017 — Fan-Out Basic

Smallest possible fan-out: items_field mode, 3 items, doubler subgraph, collect results.
Establishes the fundamental shape before testing nuances in 018-023.

**Spec sections exercised:**

- §9 Configuration table — `items_field`, `item_field`, `collect_field`, `target_field`.
- §9.1 Per-instance projection — items_field mode; each instance gets one item.
- §9.2 Concurrent execution — default `concurrency: 10`, all 3 instances run in parallel.
- §9.3 Per-instance fan-in — collected results in input order despite concurrent completion.
- §9.4 Item ordering — final `target_field` is `[2, 4, 6]` regardless of completion order.

**What passes:**

- Three subgraph instances run.
- Final `results == [2, 4, 6]` (input order preserved).
- `execution_order` shows `process` as one outer step (the fan-out node treated as a single
  dispatch from the parent's perspective).

**What fails:**

- `results` reflects completion order instead of input order.
- Fewer or more than 3 instances run.
- `execution_order` shows the inner subgraph nodes (it shouldn't — the parent sees the fan-out as
  one dispatch).
