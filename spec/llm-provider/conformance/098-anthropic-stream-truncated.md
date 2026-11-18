# 098: A Truncated Anthropic Stream Raises `provider_unavailable`

Verifies llm-provider §8.2.6 (proposal 0128). A stream that ends before `message_stop`, as a dropped
connection or a client timeout leaves it, is a connection error. The call raises `provider_unavailable`, and
the token events already emitted stand.

**Spec sections exercised:**

- llm-provider §8.2.6 *Errors*: a stream that ends before `message_stop`.
- llm-provider §8.2.3: a connection error maps to `provider_unavailable`.

**Cases:**

1. `stream_ends_before_message_stop`: content events `"Hel"` and `"lo"`, then the stream ends with no
   `message_stop`, and the call raises `provider_unavailable`.
2. `stream_ends_after_message_delta_without_message_stop`: the whole message arrives, through a
   `message_delta` carrying `stop_reason: end_turn`, and the stream ends before `message_stop`. The call
   still raises `provider_unavailable`, since only `message_stop` ends a stream.

**What passes:**

- The two token events, then the raise.

**What fails:**

- Returning a `Response` assembled from the partial stream.
- Treating a `stop_reason` on `message_delta` as the end of the stream (case 2).
- Raising a different category, such as `provider_invalid_response`.
- Dropping the token events emitted before the stream ended.
