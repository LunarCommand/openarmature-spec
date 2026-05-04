# 024 — Checkpoint Save On Every Completed Event

Verifies §10.3 save granularity for outermost-graph nodes: the engine fires
`Checkpointer.save` exactly once per node `completed` event, in step order, with each
save's record reflecting post-merge state at that node's exit.

**Spec sections exercised:**

- §10.3 Save granularity — every `completed` event from outermost-graph nodes triggers a save.
- §10.2 Checkpoint record shape — each save's record is a full state snapshot plus the
  `completed_positions` history through that point.
- §10.1.1 Registration and default behavior — Checkpointer must be explicitly registered for
  saves to fire; the fixture's `checkpointer: in_memory` is the explicit registration.

**Cases:**

1. `linear_three_node_graph_three_saves` — three-node linear graph (A → B → C) with an
   `InMemoryCheckpointer` attached. Run to completion. Assert exactly three saves, in step
   order, each carrying the cumulative `completed_positions` and post-merge state through
   that point.

**What passes:**

- Three saves, one per node's `completed` event.
- Save order matches the `completed` event delivery order.
- Each save's `state` reflects the post-merge cumulative effect of all prior nodes.
- Each save's `completed_positions` grows monotonically (one entry per save).

**What fails:**

- Save fires before `started` instead of after `completed` (wrong granularity).
- Saves are batched and a partial-batch crash loses records (the protocol mandates synchronous
  `save` returns; backends MAY batch internally but MUST flush before returning).
- A save's `state` is pre-merge for the corresponding node (wrong moment in the lifecycle).
- Implicit checkpointing fires when no Checkpointer is registered.
