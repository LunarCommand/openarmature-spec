# 103: A Streamed Anthropic Refusal With No Content Maps Like the Atomic One

Verifies llm-provider §8.2.6, §8.2.2 and §3 (proposal 0128). This is the streamed counterpart of fixture 102.
No content block arrives, and `message_delta` sets `stop_reason` and `stop_details`. The assembled message maps
by §8.2.2, so the `Response` matches the atomic one, and no token events are emitted.

**Spec sections exercised:**

- llm-provider §8.2.6: `message_delta` replaces the message's value for each key in its `delta`, among them
  `stop_reason` and `stop_details`.
- llm-provider §8.2.2 and §3: the empty-content rule for `"content_filter"`.
- llm-provider §6 *Streaming assembly*: the streamed `Response` has the atomic shape.

**Cases:**

1. `streamed_empty_refusal_maps_to_empty_content_filter`: no token events; the `Response` has `content: ""`,
   no tool calls, `"content_filter"` and usage 14, 0 and 14; `raw` holds `content: []`,
   `stop_reason: refusal` and the `stop_details` from `message_delta`.

**What passes:**

- `stream: true` on the wire, no token events, fixture 102's `Response`, and the `raw` keys.

**What fails:**

- Raising because no content block arrived.
- Leaving `stop_details` off `raw` because `message_start` did not carry it.
- Keeping `message_start`'s `null` `stop_reason`, so the finish reason is not `"content_filter"`.
