# 054 — `LlmCompletionEvent` populates `fan_out_index` for fan-out-instance LLM calls

Verifies that `fan_out_index` on `LlmCompletionEvent` is correctly populated for LLM calls that
occur inside a fan-out instance, and that sibling instances' typed events carry distinct
`fan_out_index` values. The field is part of the event-source identity tuple per graph-engine §6 —
load-bearing for sibling-instance disambiguation downstream (e.g., per-instance accumulators,
Langfuse Generation observations under per-instance Span observations).

**Spec sections exercised:**

- graph-engine §6 — `LlmCompletionEvent.fan_out_index` field (sibling-instance disambiguator).
- pipeline-utilities §9 — Fan-out per-instance dispatch.

**Cases:**

1. `llm_completion_event_fan_out_index_populated_per_instance` — Fan-out over two items. Each
   instance's subgraph contains one LLM-calling node. A custom observer collects all
   `LlmCompletionEvent`s. Asserts the observer holds two events with distinct `fan_out_index`
   values (`0` and `1`); `branch_name` is null on both (no parallel-branches scope);
   `node_name` is the inner LLM-calling node on both.

**Harness extensions:** the harness MUST support fan-out dispatch (already established by the
0029 / 029-caller-metadata fixture set) plus observer-internal storage of captured events with
observer-introspection expectations covering multiple events.

**What passes:**

- Two `LlmCompletionEvent`s are captured (one per instance).
- The two events carry distinct `fan_out_index` values (`0` and `1`); the set covers both
  instances.
- `branch_name` is null on both events (no parallel-branches scope).
- `node_name` matches the inner LLM-calling node for both events.

**What fails:**

- Only one `LlmCompletionEvent` is captured — the framework did not emit per-instance events.
- Both events carry the same `fan_out_index` — the field was not correctly populated from the
  event-source identity tuple, breaking sibling-instance disambiguation.
- `fan_out_index` is null on either event — the field was not populated despite the calling
  node running inside a fan-out instance.
- `branch_name` is populated despite no parallel-branches scope (would mean the field is being
  derived from something other than the actual dispatch context).
