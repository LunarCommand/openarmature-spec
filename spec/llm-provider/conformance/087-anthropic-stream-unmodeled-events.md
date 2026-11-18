# 087: Anthropic Stream Events and Blocks the Mapping Does Not Model

Verifies llm-provider §8.2.6 and §8.2.2 (proposal 0128). The mapping ignores `ping`, an event type it does not
recognize and a delta type it does not recognize. A `citations_delta` adds a citation to the text block on
`raw`. A block of a type the mapping does not model, here `server_tool_use`, is assembled from its events,
left out of the message and kept on `raw`. None of these emits a token event, and neither does a delta on an
unmodeled block, whatever its delta type. Events for different block indexes may interleave, and each applies
to its own block.

**Spec sections exercised:**

- llm-provider §8.2.6: ignored `ping`, event and delta types; the `citations_delta` rule; `input_json_delta`
  on a server-side tool block; the unparseable-buffer rule for an unmodeled block; no token events for a delta
  on an unmodeled block; interleaved block indexes.
- llm-provider §8.2.2: a block of an unmodeled type is left out of `message.content` and
  `message.tool_calls`, stays on `raw`, and is not an error.

**Cases:**

1. `ignored_events_citations_and_server_tool_block`: the `Response` holds the two text blocks and no tool
   calls. The token events are the two text deltas, at `chunk_index` 0 and 1. `raw.content` holds the
   `server_tool_use` block with its parsed `input`, the cited text block with a one-entry `citations` list,
   and the uncited text block with no `citations` key.
2. `unparseable_server_tool_input_is_not_an_error`: a `server_tool_use` buffer that does not parse, under
   `stop_reason: end_turn`, does not raise. The text maps, and `raw.content` holds the block with the buffer
   string as its `input`.
3. `unmodeled_block_text_delta_emits_no_event`: a `future_block` receives a `text_delta`. Only the text
   block's delta is emitted, and the message holds only the text block. How the unmodeled block assembles on
   `raw` is not asserted.
4. `interleaved_block_indexes_apply_to_their_own_blocks`: two `tool_use` blocks, at index 0 and 1, receive
   their `input_json_delta` events alternately. The calls' arguments are `{location: "SF"}` and
   `{location: "NYC"}`, and no token events are emitted.

**What passes:**

- Each `Response` and the token events, and, in cases 1 and 2, the exact `raw.content` lists.

**What fails:**

- Raising on `ping`, the unknown event, the unknown delta, or the unparseable server-tool buffer.
- Surfacing the `server_tool_use` block on `message.content` or `message.tool_calls`.
- A token event for the citation, the server-tool input or the unknown delta.
- A `citations` key on the uncited block, or a citation lost from the cited one.
- The server-tool block's `input` on `raw` left as the start event's `{}`.
- A token event for the unmodeled block's `text_delta` (case 3).
- A delta routed by block type, or to the most recently started block, instead of to the block its index
  names, which mixes the two tool inputs (case 4).
