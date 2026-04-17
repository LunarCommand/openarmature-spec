# 004 — Reducer: append

Verifies that the `append` reducer concatenates new list-typed updates onto the existing list, preserving order
and not mutating the prior list reference.

**Spec sections exercised:**
- §2 Reducer — `append` is a required reducer for list-typed fields.
- §2 Node — "A node MUST NOT mutate the state object it received."

**What passes:**
- Final `items` is `["seed", "x", "y", "z"]` (initial + node `a` + node `b`, in order).

**What fails:**
- Final `items` is `["z"]` or `["x", "y", "z"]` (reducer overwrote instead of appending).
- Final `items` is `["seed", "z", "x", "y"]` or any other out-of-order result.
- Mutation of the input list between node executions (detected by comparing object identity where the
  language supports it).
