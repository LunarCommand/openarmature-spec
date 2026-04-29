# 016 — Observer Attempt Index Default

Verifies the §6 `attempt_index` field's default behavior added by [proposal 0004]
(../../../proposals/0004-pipeline-utilities-middleware.md): for nodes not wrapped by retry
middleware (or any other middleware that re-attempts), every node event MUST carry
`attempt_index == 0`.

This is a regression-class fixture for non-retry workflows. Implementations that forgot to set
the default would either omit the field (making it implicit) or surface `null` for non-retry
nodes, both of which the spec forbids.

**Spec sections exercised:**

- §6 Node event shape — `attempt_index` field, default `0`.
- §6 "For nodes not wrapped by retry middleware (...), `attempt_index` MUST be `0`."

**What passes:**

- All three node events have `attempt_index == 0`.
- Step counter increments per node (0, 1, 2) — same as before the §6 modification.
- All other event fields match the linear-graph baseline (matches fixture 012's events
  except for the new `attempt_index` field).

**What fails:**

- `attempt_index` is missing from any event.
- `attempt_index` is `null` for any event.
- `attempt_index` increments across nodes (it should be 0 for every event in a non-retry
  workflow).
