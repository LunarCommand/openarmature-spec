# 092: Gemini Streamed Thought Parts and Signed Parts

Verifies llm-provider §8.3.6 and §8.3.2 (proposal 0128) for thought parts and parts that carry a
`thoughtSignature`. Adjacent text parts join only when they have the same `thought` value and neither is
signed. A signed part is never joined and keeps its signature. An empty signed text part becomes an empty
signed `TextBlock`, and a signed thought part becomes a signed `ThinkingBlock`. An empty unsigned text part is
left out of the message.

**Spec sections exercised:**

- llm-provider §8.3.6 *Assembly*: the joining rule, an absent `thought` read as `false`, signed parts kept
  apart, the empty signed part, and the empty unsigned part dropped after joining.
- llm-provider §8.3.6 *Token events* and §6 *Empty deltas*: reasoning and content events, none for an empty
  part.
- llm-provider §8.3.2: signature capture, the signed thought part, and the empty unsigned part.
- llm-provider §3.1.1 and §3.1.4: an empty block is valid when it carries a signature.
- llm-provider §6 *Structural identity*: the Gemini signed-part exception (cases 2 and 3).

**Cases:**

1. `streamed_thought_text_and_signed_parts`: two thought pieces, a `thought: false` piece, a piece with
   `thought` absent, two adjacent signed text parts, an unsigned text part, then a last chunk carrying an
   empty signed text part with `finishReason` and `usageMetadata`. Seven token events; six blocks.
2. `streamed_signed_thought_piece_gives_two_thinking_blocks`: an unsigned thought piece then a signed one give
   two `ThinkingBlock`s, the signature on the second only.
3. `atomic_signed_thought_part_gives_one_thinking_block`: the atomic response with the whole thought as one
   signed part gives one signed `ThinkingBlock`.
4. `empty_unsigned_part_after_function_call_left_out`: a text part, a signed `functionCall` part, then an
   empty unsigned text part. The content holds only the first text part; the call keeps its signature.

**What passes:**

- Each case's token events, in order and with no gaps.
- Each case's content as a complete, ordered block list, with signatures exactly where the parts carried
  them.
- `finish_reason` `"stop"` in cases 1 to 3 and `"tool_calls"` in case 4.

**What fails:**

- `thought: false` and an absent `thought` kept as two blocks.
- A signed part joined with a neighbor, its signature lost, or its signature moved to the joined block.
- The empty signed part dropped, or given a token event.
- A signed thought part mapped to an unsigned `ThinkingBlock`, or its signature put on a sibling block.
- An empty `TextBlock` with no signature on the message (case 4).
