# 003 — Multi-message reply, tool-calling agent (§3 + §7)

A tool-loop agent emits the canonical three-message sequence per
llm-provider §3 within one invocation: an assistant message carrying
`tool_calls` (top-level message field, NOT a content-block type), a
`tool`-role message carrying `tool_call_id` + string `content`, and a
final assistant text reply. The chat harness's tail extraction surfaces
all three on `.replies` in graph-execution order.

This fixture is the load-bearing case for the canonical-tool-call-shape
rule the chat sub-spec inherits from llm-provider §3: tool calls are
top-level message fields, NOT content blocks; tool results are separate
`tool`-role messages, NOT content blocks. Any divergence here would create
cross-spec drift between the chat-harness message shape and the
llm-provider wire shape.

**Spec sections exercised:**

- harness-chat §3 — `ChatMessage` shape (mirrors llm-provider §3)
- harness-chat §7 — outbound wiring (all-roles inclusion + graph-execution
  order)
- llm-provider §3 — canonical message shape with `tool_calls` on assistant
  messages

**What passes:**

- `.replies` has exactly three messages in append order.
- `.replies[0]` is `role: assistant` with `tool_calls` populated; `content`
  is empty (per llm-provider §3's allowance when `tool_calls` is non-empty).
- `.replies[1]` is `role: tool` with `tool_call_id: "call_abc"` matching the
  earlier assistant tool call's `id`, and string `content`.
- `.replies[2]` is `role: assistant` with text `content` (no `tool_calls`).
- Final session `messages` count is 4 (user + three replies).

**What fails:**

- Tool calls appear as content blocks instead of on the assistant message's
  `tool_calls` field — divergence from llm-provider §3.
- Tool results appear as content blocks instead of `tool`-role messages —
  same divergence.
- `.replies` re-orders the three messages — §7's graph-execution-order rule
  is broken.
