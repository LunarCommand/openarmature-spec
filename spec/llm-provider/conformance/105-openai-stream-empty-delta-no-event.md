# 105: An Empty OpenAI Delta Emits No Token Event

Verifies llm-provider §6 *Streaming assembly* and §8.1.6, and graph-engine §6's `chunk_index` (proposal
0128). An empty delta emits no `LlmTokenEvent`, and `chunk_index` counts the events the call emitted, from 0
with no gaps. OpenAI-compatible servers commonly open a stream with a chunk whose `delta.content` is `""`, so
this is the everyday case of the rule.

**Spec sections exercised:**

- llm-provider §6 *Streaming assembly*: an empty delta emits no token event.
- llm-provider §8.1.6: a token event for each non-empty content delta.
- graph-engine §6: `chunk_index` counts emitted events with no gaps.

**Cases:**

1. `empty_leading_delta_emits_no_token_event`: a leading chunk with `delta.content: ""`, then `"Hello"` and
   `" there"`. Two content token events with `chunk_index` 0 and 1, and the assembled `Response` with content
   `"Hello there"`, `finish_reason` `"stop"` and the terminal chunk's usage.

**What passes:**

- Exactly two token events, `chunk_index` 0 and 1, in order.
- The assembled `Response` as stated.

**What fails:**

- A token event for the empty delta (three events).
- A `chunk_index` that counts raw chunks, giving 1 and 2.
