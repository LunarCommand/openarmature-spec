# 096: An Anthropic Block the Mapping Does Not Model Stays on `raw`

Verifies llm-provider §8.2.2 (proposal 0128), on an atomic response. A content entry of a type the mapping
does not model is left out of `message.content` and `message.tool_calls`, stays on `raw` verbatim, and is not
an error. A text block with empty text and no `signature` is left out the same way. If no content and no tool
calls are left, the empty string is allowed only for `"content_filter"`, `"length"` or
`"error"`, and any other finish reason raises.

**Spec sections exercised:**

- llm-provider §8.2.2: the unmodeled-entry rule, the empty unsigned text rule and the empty-content rule.
- llm-provider §3 *An empty response*.

**Cases:**

1. `unmodeled_blocks_left_out_text_mapped`: a `server_tool_use` block, a `web_search_tool_result` block and a
   text block. The `Response` holds the text block only, with no tool calls and `"stop"`. `raw.content`
   holds all three blocks as received.
2. `only_unmodeled_blocks_under_end_turn_raises`: the same two server-side blocks with no text, under
   `stop_reason: end_turn`, raise `provider_invalid_response`.
3. `empty_unsigned_text_block_left_out`: an empty unsigned text block, then a non-empty one. The `Response`
   holds the second block only, and `raw.content` holds both.

**What passes:**

- The text-only `Response` with the server-side blocks on `raw`, and the raise in case 2.

**What fails:**

- Raising on the unmodeled blocks in case 1.
- Surfacing `server_tool_use` as a tool call, or either block on `message.content`.
- Dropping the blocks from `raw`.
- Returning empty content with `"stop"` in case 2.
- Raising on the empty text block, or keeping it as an empty `TextBlock`, in case 3.
