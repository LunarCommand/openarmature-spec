# 002 — Conditional Routing (Post-Update State)

Verifies that conditional edges are evaluated against **post-update** state — the state reflecting the node's
partial update — not the pre-update state the node received.

**Spec sections exercised:**
- §2 Edge — conditional edge.
- §3 Execution model, step 3 — "invoke the edge function with the post-update state."

**What passes:**
- Node `a` runs with `count == 0`, returns `{count: 1}`.
- The conditional edge evaluates against `count == 1` and routes to `END`.
- Node `b` never runs.

**What fails:**
- Routing to `b` (would indicate the edge saw pre-update `count == 0`).
- Any execution order that includes `b`.
