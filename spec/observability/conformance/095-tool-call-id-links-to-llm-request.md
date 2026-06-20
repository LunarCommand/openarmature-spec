# 095 — Tool-call id links to the LLM request

Verifies graph-engine §6 (proposal 0063): `tool_call_id` joins a tool execution to
the `LlmCompletionEvent.output_tool_calls` entry it satisfies (the observability
§5.5.10 `.ids` linkage), and is null for a standalone instrumented function.

## Spec coverage

- graph-engine §6 — `tool_call_id` is the `ToolCall.id` of the requesting
  `output_tool_calls` entry; null when the function did not originate from an LLM
  tool request.
- observability §5.5.10 — the request-side `.ids` projection is what the execution
  links back to.

## Cases

1. `llm_originated_tool_call_carries_matching_id` — an LLM returns a tool-call
   request (`call_xyz789`); the executed tool's `ToolCallEvent` carries the same
   `tool_call_id`.
2. `standalone_instrumented_function_carries_null_id` — an instrumented utility
   with no LLM origin → `tool_call_id = null`.

## Anti-cases

- A standalone instrumented function carrying a fabricated `tool_call_id`.
- The executed tool's `tool_call_id` not matching the requesting call's id.
