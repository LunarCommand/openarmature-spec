# 056 — `LlmCompletionEvent` strict-serial delivery ordering

Verifies `LlmCompletionEvent`'s placement in the strict-serial observer delivery queue (per
graph-engine §6). The spec text for the typed event says it is "dispatched on the observer
delivery queue at the point of LLM call completion (after the adapter receives a successful
response and before the call returns to the caller)" — which places the event between the
LLM-calling node's `started` `NodeEvent` (delivered before the node body runs) and its
`completed` `NodeEvent` (delivered after the node returns and the merge runs).

**Spec sections exercised:**

- graph-engine §6 — *Event delivery* strict-serial guarantee; *Typed LLM completion event*
  dispatch timing ("after the adapter receives a successful response and before the call
  returns to the caller").

**Cases:**

1. `llm_completion_event_arrives_between_node_started_and_completed` — A graph with one
   LLM-calling node. A custom observer captures every event (both `NodeEvent` and
   `LlmCompletionEvent`) in arrival order. Asserts the captured sequence contains, in this
   order:
   1. A `NodeEvent` with `phase = started` and `node_name = ask`.
   2. An `LlmCompletionEvent` for the same node (`node_name = ask`).
   3. A `NodeEvent` with `phase = completed` and `node_name = ask`.

   Other events (invocation lifecycle, etc.) MAY appear before, between, or after; the
   fixture asserts only the relative order of these three events for the LLM-calling node.

**Harness extensions:** the harness MUST support observer-internal storage that retains
captured events in arrival order, plus an observer-introspection expectation asserting the
relative order of events filtered by node name and event type.

**What passes:**

- The three events appear in the order: `NodeEvent(started)` → `LlmCompletionEvent` →
  `NodeEvent(completed)` for `node_name = ask`.
- All three events identify the same node (`node_name = ask`).

**What fails:**

- The `LlmCompletionEvent` arrives before the node's `started` `NodeEvent` (would mean the
  framework emitted the typed event from a different scope than the calling node's body).
- The `LlmCompletionEvent` arrives after the node's `completed` `NodeEvent` (would mean
  emission happens AFTER the node returns to the caller, violating the spec's
  "before the call returns" rule).
- The strict-serial guarantee is violated (two events arrive concurrently or interleaved).
