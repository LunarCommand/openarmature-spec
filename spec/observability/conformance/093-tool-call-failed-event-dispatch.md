# 093 — Tool-call failed event dispatch (failure)

Verifies graph-engine §6 (proposal 0063): an instrumented tool execution that
raises dispatches one `ToolCallFailedEvent`, and the exception re-raises.

## Spec coverage

- graph-engine §6 — the scope emits a terminal `ToolCallFailedEvent` when the
  execution raises, carrying `error_type` + `error_message`.
- **No `error_category`** on the event — the deliberate departure from
  `LlmFailedEvent` / `EmbeddingFailedEvent` (no closed llm-provider §7 taxonomy
  for arbitrary tool code).
- Exception flow — the exception re-raises out of the scope alongside the typed
  event (the node lets it propagate → invocation errors `node_exception`).
- Mutual exclusion — zero `ToolCallEvent` on a failed execution.

## Cases

1. `tool_call_failed_event_dispatched_on_raise` — a mock tool raises
   `TimeoutError`; one `ToolCallFailedEvent` (with `error_type` / `error_message`,
   no `error_category`), zero `ToolCallEvent`, and the exception propagates.

## Anti-cases

- An `error_category` field on the tool-failure event.
- The exception swallowed by the scope (it must re-raise).
- A `ToolCallEvent` emitted for a failed execution.
