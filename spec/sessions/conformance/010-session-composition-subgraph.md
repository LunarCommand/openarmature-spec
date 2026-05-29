# 010 — Subgraph Composition

Verifies §9.1: subgraphs do NOT see session state directly. They observe only the fields the
outer graph projects in via the subgraph's input/output mapping (graph-engine §2).

**Spec sections exercised:**

- §9.1 Composition with subgraphs — session state is an outermost-graph concern.
- §4.2 Projection — the SessionState projection determines which outer fields are persisted, but
  is orthogonal to the subgraph's input/output mapping.

**Cases:**

1. `subgraph_sees_only_projected_input_not_session_state` — outer graph is session-bound; inner
   subgraph receives only its declared inputs via explicit mapping. The inner subgraph never
   observes the outer session's full state.

**What passes:**

- The inner subgraph's pre-state contains only the two fields in its declared schema, populated
  per the explicit mapping (`inner_input="outer-data"`, `inner_output=""`).
- The inner subgraph performs no `SessionStore` operations of its own.
- The outer graph saves the full outer state at END (including the projected-back
  `outer_result`).

**What fails:**

- The inner subgraph receives extra fields beyond its schema (session-state leakage).
- The inner subgraph attempts a load or save against a SessionStore.
- The outer graph's save at END omits the projected-back result from the subgraph.
