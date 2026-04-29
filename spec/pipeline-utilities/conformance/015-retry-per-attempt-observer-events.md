# 015 — Retry Per-Attempt Observer Events

Verifies the load-bearing per-attempt visibility behavior: retry middleware dispatches a §6 node
event for each non-final attempt; the engine dispatches the final attempt's event; observers see
all N events in attempt order, distinguished by `attempt_index`.

This is the production observability story — OTel exporters, structured-log observers, dashboards
all consume the §6 stream and now see retry attempts as first-class events instead of being blind
to them.

**Spec sections exercised:**

- §6.1 Per-attempt observer events.
- graph-engine §6 (modified by proposal 0004) — `attempt_index` field; "Middleware-dispatched
  events" subsection; "Event dispatch" updated to "once per attempt".

**What passes:**

- Observer receives exactly 3 events.
- `attempt_index` values are `0`, `1`, `2` in order.
- Events 0 and 1 have `error == node_exception`, `post_state` absent.
- Event 2 has `post_state == {v: 7, trace: ["target"]}`, `error` absent.
- All three events share the same `node_name == "target"`, `namespace == ["target"]`,
  `step == 0`, `pre_state == {v: 0, trace: []}`, `parent_states == []`.

**What fails:**

- Only one event fires (retry didn't dispatch per-attempt events).
- `attempt_index` is missing from events (graph-engine §6 modification not applied).
- Events have `step` 0/1/2 instead of all 0 — retries were treated as separate node positions
  (wrong: same node, multiple attempts).
- The first two events have `post_state` populated (a failed attempt should have `error`, not
  `post_state`).
- Events arrive out of attempt order.
