# 094 — Tool-call event mutual exclusion

Verifies graph-engine §6 (proposal 0063): `ToolCallEvent` and `ToolCallFailedEvent`
are mutually exclusive per tool execution.

## Spec coverage

- graph-engine §6 — exactly one terminal event per execution; implementations MUST
  NOT emit both.

## Cases

1. `success_emits_only_tool_call_event` — a returning tool → 1 `ToolCallEvent`,
   0 `ToolCallFailedEvent`.
2. `failure_emits_only_tool_call_failed_event` — a raising tool → 1
   `ToolCallFailedEvent`, 0 `ToolCallEvent`.

## Anti-cases

- Both events emitted for a single execution (either direction).
