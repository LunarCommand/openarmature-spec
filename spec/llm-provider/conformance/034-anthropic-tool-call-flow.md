# 034 — Anthropic tool-call flow

Verifies the §8.2.1.2 `tool` role bidirectional translation on send, the §8.2.1.1 `tool_use`
content-block mapping, and the §4 Tool → `input_schema` mapping.

**Spec sections exercised:**

- §8.2.1.1 — a spec `ToolCall` (from the assistant `tool_calls` field) serializes to a Anthropic
  `tool_use` content block `{type, id, name, input}`; `input` is the deserialized arguments
  object (no JSON-string serialization).
- §8.2.1.2 — a spec `tool` message maps to a Anthropic `user` message carrying a `tool_result`
  block `{type, tool_use_id, content}`.
- §8.2.1 tool definitions — §4 `Tool.parameters` maps under `input_schema` (not `parameters`).

**What passes:**

- The assistant turn's `tool_calls` becomes a `tool_use` content block in the assistant message
  (`input: {location: "SF"}` as an object).
- The `tool` message becomes a `user` message with a single `tool_result` block carrying
  `tool_use_id: toolu_1` and the result content.
- The tool definition appears under `input_schema`, not `parameters`.

**What fails:**

- Tool calls emitted under a top-level `tool_calls` wire field (OpenAI shape) instead of as
  `tool_use` content blocks.
- The `tool` message emitted with a `tool` role (Anthropic has no `tool` role) instead of a
  `user` message with a `tool_result` block.
- The tool schema emitted under `parameters` instead of `input_schema`.
