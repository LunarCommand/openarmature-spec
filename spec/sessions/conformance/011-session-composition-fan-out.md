# 011 — Fan-Out Composition

Verifies §9.2: fan-out instances are subgraph invocations and therefore inherit the §9.1 rule —
they do NOT see session state directly. Per-instance state is the projection from the outer
graph, scoped to the instance's item.

**Spec sections exercised:**

- §9.2 Composition with fan-out — instances are subgraphs; session state is invisible to them
  except through projection.
- §4.2 Projection — the outer SessionState carries the items list; the fan-out projects per-item.

**Cases:**

1. `fan_out_instances_see_only_projected_per_instance_input` — outer graph is session-bound;
   fan-out node iterates over `items`; each instance sees only its single item.

**What passes:**

- Each instance's pre-state contains only its schema's two fields, with `item` set to the
  projected per-instance value.
- No instance performs a `SessionStore` operation.
- The outer graph saves the full outer state at END, including the appended `outputs` list.

**What fails:**

- An instance receives extra fields beyond its schema (session-state leakage).
- An instance attempts a load or save against a SessionStore.
- The outer graph's save at END omits the appended outputs.
