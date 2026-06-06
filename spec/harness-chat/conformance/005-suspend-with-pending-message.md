# 005 — Suspension with pending message (§8.1)

A two-node graph: an upstream `compose_pending` node returns a partial
update appending a synthetic assistant "pending" message to
`state.messages` via the standard `append` reducer; a downstream
`suspend_gate` node calls `suspend()`. The chat harness extracts the
pending message from the suspended outcome's `state.messages` tail (the
same extraction rule §7 uses for completed replies) and surfaces it on
`ChatTurnOutcome.suspended.pending_message`.

The load-bearing rule: **no chat-specific engine hook is needed**. The
pending-message pattern composes from existing graph primitives — an
upstream node returns `{messages: [pending_msg]}` partial update, an edge
routes to a downstream node that calls `suspend()`, the engine persists
the post-update state at suspend, and the chat harness sees the pending
message in the suspended outcome's tail. Any divergence (e.g., a
`chat.emit_pending()` hook on the engine) would contradict the proposal's
resolved-at-draft decision.

**Spec sections exercised:**

- harness-chat §8.1 — pending message protocol
- harness §5.3 — suspended outcome handling (load-bearing no-block rule)
- suspension §3 — `suspend()` operation

**What passes:**

- `send()` returns `ChatTurnOutcome.suspended` (not blocked, not errored).
- `.pending_message` carries the assistant message the graph appended
  before calling `suspend()`.
- `.signal_descriptor` carries the descriptor's `signal_id` + `metadata`.
- The chat harness does NOT block on the suspended outcome.

**What fails:**

- `send()` blocks waiting for the signal — would mean harness §5.3's
  no-block rule is broken at the chat-harness layer.
- `.pending_message` is empty when the graph appended one — would mean
  the tail-extraction rule isn't running over the suspended state.
- The pending message is surfaced via some non-reducer mechanism (a
  chat-specific engine hook) — would mean the resolved-at-draft "no
  engine surface change" decision is being violated.
