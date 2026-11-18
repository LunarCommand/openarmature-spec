# 084: An Anthropic Text Stream Assembles, With Merged Usage

Verifies llm-provider §8.2.6 (proposal 0128). A `stream`-set call sends `stream: true` and consumes
Anthropic's named server-sent events. The mapping rebuilds the atomic `Message` from the events and maps it by
§8.2.2, so the streamed `Response` has the shape of the atomic one.

**Spec sections exercised:**

- llm-provider §8.2.1: the body `stream` field realizes the declared `stream` argument.
- llm-provider §8.2.6: assembly from `message_start`, the content block events and `message_delta`; the
  per-key usage merge; content token events per non-empty `text_delta`.
- llm-provider §6 *Streaming assembly*: an empty delta emits no token event.
- graph-engine §6: `chunk_index` counts the events emitted, from 0 with no gaps.
- llm-provider §8.2.2: the cache counts are not promoted to the §6 cache fields.

**Cases:**

1. `text_stream_assembles_with_merged_usage`: three non-empty `text_delta` events with an empty one between
   the first and second. The token events are `"Hello"`, `", "` and `"world."` with `chunk_index` 0, 1 and 2.
   The `Response` holds one text block, `"Hello, world."`, with `"stop"`. Usage is `prompt_tokens` 25 from
   `message_start` and `completion_tokens` 15 from `message_delta`, with `total_tokens` 40. `raw` holds the
   merged `usage` and `stop_reason: end_turn`.

**What passes:**

- `stream: true` on the wire, the three token events in order with no gap, the assembled `Response`, and the
  merged usage on both the `Response` and `raw`.

**What fails:**

- A token event for the empty delta, or `chunk_index` 0, 2, 3, which leaves a hole where the empty delta was.
- Usage taken from `message_delta` alone, which gives no `prompt_tokens`.
- Usage taken from `message_start` alone, which gives `completion_tokens` 1.
- `message_delta`'s `usage` replacing the whole usage record, which drops `input_tokens` and the cache counts
  from `raw`.
- `cached_tokens` or `cache_creation_tokens` set from the cache counts.
