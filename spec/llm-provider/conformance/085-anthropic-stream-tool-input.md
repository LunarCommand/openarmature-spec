# 085: Anthropic Streamed Tool Input Is Buffered and Parsed at the Block's End

Verifies llm-provider §8.2.6 (proposal 0128). A `tool_use` block's input arrives as `input_json_delta`
events. The mapping appends each `partial_json` to a buffer that starts empty, whatever `input` the start
event carries, and parses the buffer at `content_block_stop`. An empty buffer keeps the start event's `input`.
A buffer that does not parse becomes the block's `input` as a string. The tool call is then malformed: its
`arguments` are `null` under a `stop_reason` that maps to `"error"`, and otherwise the response raises.

**Spec sections exercised:**

- llm-provider §8.2.6: `input_json_delta` buffering, the empty-buffer rule and the unparseable-buffer rule.
- llm-provider §6 *Streaming assembly*: tool-call deltas emit no token events, and unparseable arguments are
  `null` under `"error"` and otherwise raise.
- llm-provider §3 *Validation under `finish_reason: "error"`*.
- llm-provider §8.2.2: `tool_use` maps to `"tool_calls"` and an unknown `stop_reason` to `"error"`.
- llm-provider §8.2.6 *Structured output* and §8.2.5.1: on the tool-coercion path the structured content
  emits no token events, and `parsed` is validated from the assembled input.

**Cases:**

1. `split_input_parses_and_empty_input_keeps_start_value`: the first block's JSON is split mid-token across
   three deltas, with `input: {}` on its start event, and gives `{location: "SF"}`. The second block has no
   deltas and gives `{}`. No token events, and `"tool_calls"`.
2. `unparseable_input_under_tool_use_raises`: a cut-off buffer under `stop_reason: tool_use` raises
   `provider_invalid_response`, with no token events.
3. `unparseable_input_under_unknown_stop_reason_gives_null_arguments`: the same buffer under an unlisted
   `stop_reason` gives `finish_reason: "error"`, the tool call with `arguments: null`, and `raw` holding the
   buffer string as the block's `input`.
4. `streamed_tool_coercion_parses_and_emits_no_content_events`: gated on `anthropic_fallback_tool_coercion`.
   A streamed call on a model without native structured output takes the tool-coercion path, sending the
   synthetic tool and a `tool_choice` naming it. The synthetic tool's input is split across two deltas, no token events are emitted, and `parsed` is `{value: 42}`.

**What passes:**

- Parsed arguments for the split input, `{}` for the empty buffer, the raise in case 2 and the `null`
  arguments with the verbatim buffer on `raw` in case 3.
- In case 4, a request carrying the synthetic tool with the schema as its `input_schema` and a `tool_choice`
  naming it, no token events, and `parsed` equal to `{value: 42}`.

**What fails:**

- Parsing each delta on its own, or merging the buffer into the start event's `{}` instead of replacing it.
- Treating an empty buffer as unparseable, which fails case 1's second call.
- Emitting tool-input deltas as token events.
- Returning `null` arguments under `"tool_calls"`, or raising under `"error"`.
- Dropping the unparseable bytes from `raw`, or keeping the start event's `{}` there.
- Emitting the synthetic tool's input as content token events, or `parsed` missing on the streamed
  coercion call (case 4).
