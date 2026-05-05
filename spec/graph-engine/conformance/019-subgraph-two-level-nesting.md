# 019 — Subgraph Two-Level Nesting

Verifies that the §6 depth-extending invariants — `namespace` chain, `parent_states` stack, and `step`
counter — hold correctly when subgraphs are nested two levels deep. Existing subgraph fixtures (006,
011, 013) only exercise depth 1; this fixture exercises depth 2 so the recursion in
`descend_into_subgraph` and the projection chain are tested at a second level.

**Spec sections exercised:**

- §2 Subgraph — projection at every level uses field-name matching (the default `ProjectionStrategy`).
  The inner subgraph's exit values project into the middle subgraph; the middle subgraph's exit values
  project into the outer graph.
- §6 Observer hooks — the depth invariants are asserted at each transition:
  - `len(parent_states) == len(namespace) - 1` at depth 3 (namespace length 3, parent_states length 2).
  - `step` is monotonic across both subgraph boundaries (0 outer, 1 middle, 2-3 inner, 4 middle, 5 outer).
  - `parent_states[k]` is the k-th containing graph's state at the moment that graph entered the
    subgraph-as-node leading to this event. Snapshots are stable for the duration of the inner run —
    inner_p and inner_q share identical `parent_states` because neither the outer nor the middle is
    stepping while the inner runs.

**Structure under test:**

```
outer:  outer_a -> outer_mid -> outer_b
middle: mid_x   -> mid_inner -> mid_y
inner:  inner_p -> inner_q
```

`outer_mid` references the middle subgraph; `mid_inner` references the inner subgraph.

**What passes:**

- Outer execution order is `[outer_a, outer_mid, outer_b]` — the middle subgraph appears as a single
  outer step.
- All 12 observer events fire (6 nodes × 2 phases) on the outer-attached observer. The 4 inner-subgraph
  events carry namespace `[outer_mid, mid_inner, inner_p|inner_q]` (length 3) and `parent_states`
  containing two entries (length 2).
- `parent_states[0]` for inner-node events is `{v: 1, trace: ["outer_a"]}` — the outer state at entry to
  `outer_mid`.
- `parent_states[1]` for inner-node events is `{v: 10, trace: ["mid_x"]}` — the middle state at entry to
  `mid_inner`.
- `step` values are 0, 1, 2, 3, 4, 5 in execution order across all three depths.
- Final outer state has `trace` containing the inner subgraph's `["inner_p", "inner_q"]` entries,
  appended into the middle's trace, then appended into the outer's trace.

**What fails:**

- Inner-event `parent_states` of length other than 2, or in the wrong order (innermost-first instead of
  outermost-first).
- Inner-event `namespace` shorter than 3 (would mean the chain didn't extend across the second
  boundary).
- `step` resetting at a subgraph boundary (would mean the counter wasn't shared via reference across
  contexts).
- Inner-event `pre_state` reflecting the outer's state shape rather than the inner's defaults
  (projection mistakenly bypassed).
- Final outer `trace` missing `"inner_p"` or `"inner_q"` (subgraph projections not propagating through
  both boundaries).

**Fixture format note:**

This is the first graph-engine fixture to use the plural `subgraphs:` form (a map of named subgraphs at
the top level). The format is already used in observability and pipeline-utilities fixtures (e.g.
`observability/008`, `pipeline-utilities/029`) and is documented in §2. Implementations whose
conformance harness only handles the singular `subgraph:` form will need a small adapter change to
build the named subgraphs in topological order (innermost first) before compiling the outer graph.

**Coverage classification:**

This is a **regression / clarification fixture** per `GOVERNANCE.md` — no new spec behavior is
introduced. The §6 invariants and projection rules already specify the depth-extending behavior; this
fixture only exercises a depth that no existing fixture happens to reach. No proposal required.
