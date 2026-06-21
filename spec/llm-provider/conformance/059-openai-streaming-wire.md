# 059 — OpenAI-compatible streaming wire path

Verifies the llm-provider §8.1.6 streaming wire path. `complete(stream=True)` sends `stream: true` plus `stream_options: {include_usage: true}`, consumes the Server-Sent Events response, and assembles the atomic `Response` per §6 *Streaming assembly*. The assembled `Response` (content, tool calls, usage, finish_reason) MUST equal the equivalent non-streamed response — streaming is a delivery concern, not a `Response`-shape change. This fixture introduces the streaming wire directives (`call.stream`, the `stream`/`stream_options` request fields, and `mock_provider` `stream_body`) documented in its YAML header per conformance-adapter §3.2.

**Spec sections exercised:**

- llm-provider §8.1.6 — request adds `stream: true` + `stream_options.include_usage`; SSE `data:` chunks with `choices[].delta`; content deltas concatenate; tool-call deltas reassemble; usage / finish_reason from the terminal chunks; `[DONE]` sentinel; reasoning extension (`reasoning_content` / `reasoning`).
- llm-provider §6 *Streaming assembly* — structural identity of the assembled `Response` with the non-streamed equivalent (content, tool calls, reasoning blocks, usage).

**Cases:**

1. `streamed_content_assembles_equal_to_non_streamed` — Content-only stream (`"Hello"`/`", "`/`"world."`), finish_reason on the last content chunk, terminal usage chunk, `[DONE]`. Asserts the wire request carries `stream:true` + `stream_options.include_usage:true`, and the assembled `Response` is content `"Hello, world."`, finish_reason `stop`, usage `{7,3,10}`.
2. `streamed_tool_calls_reassemble_equal_to_non_streamed` — A streamed tool call (opening `tool_calls` delta then `function.arguments` fragments), finish_reason `tool_calls`. Asserts the reassembled `tool_calls` (`id` `call_s9`, name `get_weather`, `arguments` parsing to `{city: "Paris"}`) equal the non-streamed equivalent.
3. `streamed_reasoning_extension_assembles_into_reasoning_block` — The reasoning extension: `reasoning_content` deltas stream before content. Asserts the assembled `message.content` is a content-block sequence carrying a `ThinkingBlock` (the reasoning) then a text block (the answer), shape-identical to a non-streamed reasoning response.

**What passes:**

- The wire request carries `stream: true` and `stream_options: {include_usage: true}`.
- The assembled `Response` content / tool_calls / usage / finish_reason equal the non-streamed equivalent.
- Tool-call argument deltas reassemble and parse; reasoning deltas assemble into a thinking block.

**What fails:**

- The wire request omits `stream` or `stream_options.include_usage` (usage would be lost).
- The assembled content / tool_calls differ from the non-streamed shape (truncated arguments, missing usage, wrong finish_reason).
- Reasoning deltas dropped or merged into `message.content` text instead of a thinking block.
