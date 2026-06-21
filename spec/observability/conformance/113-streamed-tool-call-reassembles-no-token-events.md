# 113 — Streamed tool-call deltas reassemble, emit no token events

Verifies llm-provider §6 *Streaming assembly* together with graph-engine §6: streamed tool-call argument deltas are reassembled into the terminal `Response.message.tool_calls` (surfaced on `LlmCompletionEvent.output_tool_calls`) but are NOT emitted as `LlmTokenEvent`s. `LlmTokenEvent` carries answer content only; the reassembly is provider-internal. This locks the "reassemble into the atomic `Response`, don't emit as token events" contract from proposal 0062.

**Spec sections exercised:**

- llm-provider §6 *Streaming assembly* — streamed tool-call argument deltas reassemble into complete `ToolCall` records on `message.tool_calls`, parsing identically to the non-streamed case; NOT emitted as token events.
- graph-engine §6 — `LlmTokenEvent.delta_kind` carries `content` only in this version (`tool_call` is reserved, not emitted); `LlmCompletionEvent.output_tool_calls` surfaces the reassembled tool calls.

**Cases:**

1. `tool_call_deltas_reassemble_only_content_token_events` — A `stream=True` call whose mock yields a content preamble `"Looking "` then OpenAI-shaped tool-call argument deltas (opening delta with `index`/`id`/`function.name`, then `function.arguments` string fragments), a terminal `finish_reason=tool_calls` chunk, and a usage chunk. Asserts exactly one `LlmTokenEvent` (`delta_kind="content"`, `"Looking "`), zero token events of any other kind, and the terminal `LlmCompletionEvent.output_tool_calls` reassembled to `[{id: call_w1, name: get_weather, arguments: {city: "Paris"}}]`.

**What passes:**

- Only the content delta produces a token event; the tool-call argument deltas produce none.
- No `LlmTokenEvent` with `delta_kind="tool_call"` is emitted (the reserved kind is not surfaced in this version).
- The terminal `LlmCompletionEvent.output_tool_calls` is the complete reassembled tool call, `arguments` parsing to the same mapping as the non-streamed equivalent.

**What fails:**

- A token event emitted for any tool-call argument delta (tool-call deltas leaking onto the token stream).
- The reassembled `output_tool_calls` incomplete (truncated arguments) or with unparsed argument fragments.
- More than one `LlmCompletionEvent`.
