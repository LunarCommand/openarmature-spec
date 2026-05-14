# 035 — Parallel Branches With Different State Schemas

Three branches whose subgraph state schemas have nothing in common: one is
purely numeric (three int fields), one carries a single string, the third
holds a list, an int, and a dict. Verifies §11.1.1's "different branches MAY
reference different compiled subgraphs with different state schemas" claim —
the engine handles each branch's state independently with no coercion to a
shared shape.

**Spec sections exercised:**

- §11.1.1 Branch spec — `subgraph` per-branch references; branches MAY
  reference different compiled subgraphs.
- §11.4 Per-branch projection (out) — each branch's `outputs` mapping
  references its own subgraph's fields; the engine reads from each branch's
  exit state independently.

**What passes:**

- All three branches' contributions land correctly:
  - `numeric_sum == 42` from the numeric branch.
  - `text_message == "hello"` from the textual branch.
  - `collected_items`, `collected_count`, `collected_labels` from the
    collection branch (a single branch contributing to three parent fields
    via three `outputs` mappings).

**What fails:**

- Any field at its default — would mean the branch didn't contribute or the
  output projection failed.
- The engine coerces the branches to a shared state shape and fields are
  cross-contaminated.
- The collection branch's multi-field `outputs` mapping doesn't apply all
  three contributions.
