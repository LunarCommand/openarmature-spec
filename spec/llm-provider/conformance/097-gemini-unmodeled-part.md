# 097: A Gemini Part of an Unmodeled Type Stays on `raw`

Verifies llm-provider §8.3.2 and §8.3.6 (proposal 0128). A part of a type the mapping does not model is left
out of `message.content` and `message.tool_calls`, kept on `raw` verbatim, and is not an error. Streamed, it
emits no token event and keeps its place in arrival order, so the text parts on either side of it are not
joined. An `executableCode` part stands for any unmodeled type.

**Spec sections exercised:**

- llm-provider §8.3.2: the unmodeled-part rule.
- llm-provider §8.3.6 *Assembly* and *Token events*: an unmodeled part separates text parts and emits no
  event.

**Cases:**

1. `streamed_unmodeled_part_between_text_parts`: streamed; two content events, two `TextBlock`s, and
   `raw.candidates` with all three parts in order.
2. `atomic_unmodeled_part_between_text_parts`: atomic; the same two `TextBlock`s, and `raw` as received.

**What passes:**

- Both cases return two `TextBlock`s, `"Before."` and `"After."`, and `"stop"`.
- The `executableCode` part is on `raw` and nowhere on the message.

**What fails:**

- `provider_invalid_response`, or any error, on the unknown part.
- The part surfaced as a block or a tool call.
- `"Before.After."` as one block, from joining across the unmodeled part.
- A token event for the part.
- The part dropped from `raw`.
