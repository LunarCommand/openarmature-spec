# 045 — Gemini function-call flow

Verifies §8.3.1.2 `tool` role bidirectional translation, the §8.3.1.1 `functionCall` part mapping,
and the §4 Tool → `functionDeclarations` mapping.

**Spec sections exercised:**

- §8.3.1.1 — a spec `ToolCall` (assistant `tool_calls`) serializes to a `functionCall` part
  `{name, id, args}` on a `model`-role `Content`; `args` is the deserialized object.
- §8.3.1.2 — a spec `tool` message maps to a `user`-role `Content` carrying a `functionResponse`
  part `{name, id, response}`; the string content wraps as `{result: <content>}`.
- §8.3.1 tool definitions — a §4 `Tool` maps under `tools[].functionDeclarations[]`.

**What passes:**

- The assistant `tool_calls` becomes a `functionCall` part on a `model` Content.
- The `tool` message becomes a `user` Content with a `functionResponse` part; content wrapped as
  `{result: "72F sunny"}`.
- The tool appears under `tools[].functionDeclarations[]` (not a top-level `tools` array of
  `{name, ...}`).

**What fails:**

- Tool calls emitted under a top-level `tool_calls` wire field (OpenAI shape) instead of
  `functionCall` parts.
- The `tool` message emitted with a `tool` role instead of a `user` Content with a
  `functionResponse` part.
- The `functionResponse.response` carrying a bare string instead of `{result: ...}`.
