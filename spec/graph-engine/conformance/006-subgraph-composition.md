# 006 — Subgraph Composition

Verifies that a compiled subgraph can be used as a single node in an outer graph. The subgraph sees a
projection of the parent's state (fields sharing names), runs its own execution model to completion, and its
final partial update is merged back into the parent using the parent's reducers.

**Spec sections exercised:**
- §2 Subgraph — "projected onto the subgraph's state schema … merged back into the parent."
- §2 Node — subgraphs compose as nodes; execution order at the outer level treats the subgraph as one unit.

**What passes:**
- Outer execution order is `[outer_a, outer_sub, outer_b]` — the subgraph appears as a single step.
- `message` ends as `"from-y"` (subgraph's last write, merged via the outer's `last_write_wins`).
- `trace` ends as `["outer-start", "outer_a", "x", "y", "outer_b"]` — initial default + outer_a + subgraph's
  inner trace (`["x", "y"]`) appended into outer's `trace` via `append`.

**What fails:**
- Outer execution order including `x` or `y` (would mean the subgraph was flattened instead of composed).
- `trace` missing the inner `"x"` and `"y"` entries (subgraph result not merged back).
- `trace` containing duplicate `"outer-start"` (subgraph re-applied the default instead of projecting).

**Projection rule:**
This fixture verifies the field-name-matching projection rule specified in §2 Subgraph — parent fields with
names matching subgraph fields are passed in, and the subgraph's final values for those fields are merged
back via the parent's reducers. Alternative projection strategies (e.g., explicit input/output mappings) are
out of scope for this fixture; see proposal 0002 for the explicit-mapping extension.
