# 055 — `LlmCompletionEvent` populates `branch_name` for parallel-branches LLM calls

Verifies `branch_name` on `LlmCompletionEvent` is correctly populated for LLM calls that occur
inside a parallel-branches branch, with sibling branches' typed events carrying distinct
`branch_name` values. Companion fixture to 054 (`fan_out_index` population). Together they
exercise the event-source identity tuple's two dispatch-context disambiguators on the typed
event surface.

**Spec sections exercised:**

- graph-engine §6 — `LlmCompletionEvent.branch_name` field (parallel-branches sibling
  disambiguator); `fan_out_index` null when outside fan-out scope.
- pipeline-utilities §11 — Parallel-branches dispatch.

**Cases:**

1. `llm_completion_event_branch_name_populated_per_branch` — A parallel-branches node with two
   named branches (`fast`, `slow`). Each branch's subgraph contains one LLM-calling node. A
   custom observer collects all `LlmCompletionEvent`s. Asserts: the observer holds two events
   with distinct `branch_name` values covering `{fast, slow}`; `fan_out_index` is null on both
   (no fan-out scope); `node_name` matches the inner LLM-calling node on both.

**Harness extensions:** the harness MUST support parallel-branches dispatch (established by
the 0044 fixture set) plus observer-internal storage of captured events with
observer-introspection expectations covering multiple events.

**What passes:**

- Two `LlmCompletionEvent`s are captured (one per branch).
- The two events carry distinct `branch_name` values covering `{"fast", "slow"}`.
- `fan_out_index` is null on both events (no fan-out scope).
- `node_name` matches the inner LLM-calling node for both events.

**What fails:**

- `branch_name` is null on either event — the field was not populated despite the calling
  node running inside a parallel branch.
- Both events carry the same `branch_name` — sibling-branch disambiguation broken.
- `fan_out_index` is populated despite no fan-out scope — the field is being derived from
  something other than the actual dispatch context.
