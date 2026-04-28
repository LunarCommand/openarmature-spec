# 014 — Observer Error Event

Verifies that a node event for a *failing* node is dispatched to observers with `error` populated and
`post_state` absent, and that the engine then propagates the error to the caller unchanged from its §4
contract.

The fixture format used here is documented in fixture 012's `.md`.

**Spec sections exercised:**

- §6 Node event shape — exactly one of `post_state` or `error` MUST be populated per event; on a failed
  node, `error` carries the §4 category identifier.
- §6 Event dispatch — for a failed execution, the event MUST be dispatched before the error propagates
  to the caller.
- §4 Error semantics — the engine's `node_exception` propagation is unchanged by the observer hook;
  observers see the failure but cannot alter it.

**What passes:**

- The observer receives exactly two events:
  1. `ok_node` — successful, with `post_state` populated and no `error`.
  2. `fail_node` — failed, with `error: node_exception` populated and no `post_state`.
- The engine raises a `node_exception` to the caller after the second event has been dispatched. The
  raised error carries recoverable state per §4.
- `pre_state` for the failing node reflects the state the node received before raising — the engine
  does not invent a post-update state for a node that never returned.

**What fails:**

- The failing node's event has both `post_state` and `error` populated, or neither.
- The failing node's event has `post_state` populated with the pre-update state (i.e., the engine
  pretended the node succeeded with no update). The spec requires `error` and absent `post_state`.
- The error propagates to the caller before the observer event for the failing node is dispatched.
- The observer is not invoked for the failing node at all (silent skip on failure).
