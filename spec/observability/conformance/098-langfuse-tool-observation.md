# 098 — Langfuse Tool observation

Verifies observability §8.4.6 (proposal 0063): tool executions render as Langfuse's
dedicated `Tool` observation type, not a `Generation`.

## Spec coverage

- §8.4.6 — the observation type is `Tool` (`asType: "tool"`), nested under the
  calling node's `Span`.
- `tool.input` / `tool.output` payload-gated per `disable_provider_payload`;
  `tool_name` / `tool_call_id` in metadata.
- Level — `DEFAULT` on `ToolCallEvent`; `ERROR` (with `error_type` / `error_message`
  in metadata) on `ToolCallFailedEvent`.

## Cases

1. `tool_execution_renders_dedicated_tool_observation` — success (payload on) →
   `Tool` observation, `DEFAULT`, input / output populated, identity in metadata.
2. `failed_tool_execution_renders_error_level` — failure → `Tool` observation at
   `ERROR` with `error_type` / `error_message`.

## Anti-cases

- Rendering the tool call as a `Generation` with `metadata.operation = "tool"`.
- Populating `input` / `output` under the default payload-off posture.
