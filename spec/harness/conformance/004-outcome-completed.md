# 004 — Completed outcome handling (§5.1)

The harness exposes the final state to the inbound caller via a
transport-shaped surface that's observably distinct from suspended
and errored outcomes. The exact transport surface is
implementation-defined; the contract requires that completion is
observably distinct.

**Spec sections exercised:**

- harness §5.1 — completed outcome handling
- harness §4 — turn lifecycle (completion path)

**What passes:**

- Invoke returns completed with `final_state.value == 42`.
- Harness surfaces a "completion_response"-shaped outbound (distinct
  from "error_response" or "suspended_acknowledgment").
- Outbound payload includes the final state.

**What fails:**

- Outbound shape is the same as error or suspended responses — would
  mean §5.1's observability requirement is broken.
- Outbound payload omits the final state — would mean the harness
  isn't exposing what completion brought.
