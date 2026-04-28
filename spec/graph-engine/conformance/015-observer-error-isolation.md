# 015 — Observer Error Isolation

Verifies that an observer raising during event delivery does NOT (a) prevent other observers from
receiving the same event, (b) prevent any observer from receiving subsequent events, or (c) propagate
to the graph caller. The §6 isolation contract is what makes observers safe to attach in production
without taking on a graph-killing failure mode.

The fixture format used here is documented in fixture 012's `.md`.

**Spec sections exercised:**

- §6 Event delivery — "An observer that raises an error MUST NOT interrupt the graph run, MUST NOT
  prevent other observers from receiving the same event, and MUST NOT prevent any observer from
  receiving subsequent events."
- §6 Event delivery — implementations SHOULD report observer errors through a language-idiomatic
  warning channel.

**What passes:**

- `obs_recorder` receives all three node events (`a`, `b`, `c`) in monotonic-step order.
- `obs_raiser` is delivered each event before `obs_recorder` (registration order); each delivery
  raises; the engine catches each, surfaces a warning, and continues to deliver the same event to
  `obs_recorder`.
- After each `obs_raiser` failure, the next event is still dispatched and delivered to both observers
  — the queue does not halt on observer error.
- The graph run completes; `final_state` and `execution_order` match the no-observer baseline.
- `invoke()` returns without raising — `obs_raiser`'s exceptions stay inside the delivery queue.

**What fails:**

- `obs_recorder` receives fewer than three events — `obs_raiser`'s failure prevented delivery of the
  same event or of subsequent events to other observers.
- `invoke()` propagates `obs_raiser`'s exception to the caller — observer errors must not be visible at
  the invocation boundary.
- The graph run halts after `obs_raiser`'s first failure — observer errors must not interrupt the
  graph.
- Final state is not equal to the no-observer baseline — the observer somehow perturbed graph state.

**Note on warning channel.**

The §6 SHOULD on the warning channel is not asserted by this fixture. The fixture verifies the MUST-level
isolation guarantees only. A separate language-specific test in each implementation may verify the
warning channel emission (e.g., Python: `pytest.warns`).
