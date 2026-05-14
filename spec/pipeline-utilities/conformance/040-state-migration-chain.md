# 040 — State Migration Chain

Two-hop migration chain: saved at `v1`, current at `v3`, two registered
migrations (`v1 -> v2` and `v2 -> v3`). Chain resolution finds the path
and applies both migrations in order; the resumed run sees the final `v3`
shape.

**Spec sections exercised:**

- §10.12.2 Chain resolution — multi-edge chain: the engine builds the
  migration graph, finds a path, and applies migrations in order.
- §10.12.2 ordering invariant — each migration's output becomes the next
  migration's input.

**What passes:**

- Both migrations run exactly once.
- Migrations run in the right order (`v1 -> v2` first, then `v2 -> v3`).
- Final state has both `v2_field` and `v3_field` populated with their
  defaults; `x` preserved from the seeded v1 state.

**What fails:**

- Only one migration runs (chain resolution didn't find the path).
- Migrations run in the wrong order (would corrupt the chain).
- `v3_field` or `v2_field` is absent (would mean a migration's output
  wasn't propagated to the next step).
