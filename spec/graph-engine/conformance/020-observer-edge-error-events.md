# 020 — Observer Edge-Error Events

Verifies the §3 step 3 (revised under proposal 0012) + §6 (revised) contract: edge-resolution
failures (`routing_error`, `edge_exception`) land on the preceding node's `completed` event with
the `error` field populated, sharing that node's started/completed pair rather than producing a
separate event pair.

This makes edge-resolution failures uniform with the other three §4 runtime error categories
(`node_exception`, `reducer_error`, `state_validation_error`) which already land on the
node's completed event with `error` populated. Observer code that handles `error`-populated
completed events (§4.2 status mapping in observability backends) picks up routing/edge errors
automatically without per-category special-casing.

**Spec sections exercised:**

- §3 step 3 (revised) — completed event fires AFTER edge evaluation; failure list extended to
  include `routing_error` and `edge_exception`.
- §6 (revised, lines 306-308 area) — routing_error and edge_exception share the preceding
  node's event pair; observer applies standard status-mapping path.
- §4 runtime categories — `routing_error`, `edge_exception` definitions unchanged; only their
  §6 propagation path changes.

**Cases:**

1. `routing_error_lands_on_preceding_node_completed` — two-node graph; node A's conditional
   edge resolves to a destination not in the graph. Single started/completed pair on A; the
   completed event has `error.category: routing_error`; node B never runs (no events).
2. `edge_exception_lands_on_preceding_node_completed` — two-node graph; node A's conditional
   edge function raises. Single started/completed pair on A; the completed event has
   `error.category: edge_exception`; node B never runs.

**What passes:**

- Each sub-case produces exactly one started/completed pair (on the preceding node).
- The completed event carries `error` populated with the correct §4 category and `post_state`
  absent.
- The downstream node never runs and produces no observer events.
- The error propagates to the `invoke()` caller as a `RuntimeGraphError` of the matching
  category with `recoverable_state` populated (per §4 recoverable_state contract).

**What fails:**

- A second event pair fires for the routing/edge error (would mean the implementation didn't
  apply the §6 revision).
- The preceding node's completed event has `post_state` populated rather than `error` (would
  mean the engine didn't fold the edge failure into the completed event).
- Node B fires a started or completed event despite never running.
- The error category on the completed event mismatches (e.g., `node_exception` instead of
  `routing_error`).

**Implementation note (informative):**

Implementations should move the `completed` event dispatch from before edge evaluation (the
v0.8.x position) to after edge evaluation. The existing failure-capture path that handles
`node_exception` / `reducer_error` / `state_validation_error` extends naturally to cover the
two edge-resolution categories — same `error`-populated dispatch, same observer handler. No
new event flow, no observer-side code path additions.
