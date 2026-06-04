# 010 — Suspended phase NodeEvent

The observer sees a `suspended` phase NodeEvent with the `descriptor`
field populated. The suspending node emits exactly one `started` event
followed by exactly one `suspended` event; `completed` does NOT
appear (per graph-engine §6's mutually-exclusive-terminal-phases
rule).

**Spec sections exercised:**

- graph-engine §6 — `phase` enum extended with `"suspended"`;
  `descriptor` field populated only on `suspended` events; mutually
  exclusive terminal phases.
- suspension §3 — `suspend()` is the node's terminal action; engine
  emits `suspended` in place of `completed`.

**What passes:**

- The observer's event stream contains exactly two events for the
  gate node: one `started`, one `suspended`.
- The `suspended` event carries the `descriptor` field matching the
  caller-supplied descriptor.
- No `completed` event for the gate node appears.

**What fails:**

- A `completed` event for the gate node appears — would mean the
  mutually-exclusive-terminal-phases rule is broken.
- The `suspended` event does NOT carry the descriptor — would mean
  the graph-engine §6 `descriptor` field is not populated on the
  `suspended` phase.
- Event order is wrong (e.g., `suspended` before `started`) — would
  mean event dispatch ordering is broken.
