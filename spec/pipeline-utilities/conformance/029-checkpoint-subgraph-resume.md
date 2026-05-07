# 029 — Subgraph Resume

Verifies §10.3 + §10.4 for subgraph-internal saves and resume re-entry. A subgraph aborts
during its second inner node; the saved record captures the first inner node's completion
plus `parent_states` describing the outer state at subgraph entry; on resume, the engine
uses `parent_states` to re-enter the subgraph and resumes at the failed inner node without
re-running the first.

This is the contrast case to fan-out atomic restart (fixture 028): subgraph internals DO
fire saves and resume DOES re-enter at any inner-node boundary. Fan-out internals do NOT
in v1. The two patterns are intentionally asymmetric.

**Spec sections exercised:**

- §10.3 Save granularity — subgraph-internal `completed` events fire saves with
  `parent_states` populated.
- §10.2 Checkpoint record shape — `parent_states` is the load-bearing field for subgraph
  re-entry.
- §10.4 step 5 — engine determines resume entry point from `completed_positions`;
  subgraph re-entry uses `parent_states`.

**Cases:**

1. `subgraph_aborts_in_inner_node_two_resume_re_enters_at_inner_two` — outer dispatches
   subgraph "inner" (two inner nodes); inner's second node raises on first run; saved
   record captures inner's first node as completed with `parent_states` populated; on
   resume, the engine re-enters the subgraph, skips the first inner node, runs the second.

**What passes:**

- Saved record's `completed_positions` includes the first inner node with `namespace:
  ["dispatch"]` — the parent graph's wrapper-node name (the one carrying `subgraph: inner`),
  matching the §6 namespace convention established by graph-engine fixture 013 (which uses
  `namespace: [outer_sub, inner_x]` for inner nodes of a subgraph dispatched by `outer_sub`).
- Saved record's `parent_states` is populated and outermost-first per graph-engine §6
  semantics.
- On resume, the first inner node is NOT re-executed; the second inner node runs.
- The subgraph as a whole completes during resume; the outer dispatch node completes;
  final state matches what an uninterrupted run produces.

**What fails:**

- Subgraph internals do not save (would mean §10.3's "subgraph internals fire saves" rule
  is not honored).
- `parent_states` is absent or empty when the saved record's position is inside a subgraph.
- On resume, the engine restarts the subgraph from its entry instead of re-entering at the
  failed inner node — `parent_states` exists but is not consulted.
- On resume, the engine treats the subgraph as a black box and re-runs everything inside it
  (would lose the subgraph-resume capability that distinguishes it from fan-out atomic
  restart).
