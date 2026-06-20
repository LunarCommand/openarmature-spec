# 092 — Tool-call event dispatch (success)

Verifies graph-engine §6 + observability §5.5.12 (proposal 0063): an instrumented
tool execution returning a result dispatches one `ToolCallEvent`.

## Spec coverage

- graph-engine §6 — the tool-call instrumentation scope emits a terminal
  `ToolCallEvent` when the execution returns a result.
- The event carries the identity / scoping baseline + `tool_name`, `tool_call_id`,
  `arguments`, `result`, `latency_ms`.
- Mutual exclusion — zero `ToolCallFailedEvent` on a successful execution.

## Cases

1. `tool_call_event_dispatched_on_result` — a mock tool returns a result; one
   `ToolCallEvent` is observed with the full field set, zero
   `ToolCallFailedEvent`.

## Anti-cases

- Both `ToolCallEvent` and `ToolCallFailedEvent` for one execution.
- `tool_call_id` dropped when the execution satisfies a model request.
- The event missing `result` or the identity / scoping fields.
