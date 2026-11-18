# 088: An Anthropic In-Stream Error Event Raises Its Mapped Category

Verifies llm-provider §8.2.6 (proposal 0128). Anthropic can send an `error` event inside a stream that began
with HTTP 200. The mapping maps its `error.type` through §8.2.3's table, as the HTTP response with that type
would map, and maps a type the table does not list to `provider_unavailable`. The call raises even when events
follow the error, and the token events already emitted stand.

**Spec sections exercised:**

- llm-provider §8.2.6 *Errors*.
- llm-provider §8.2.3: `rate_limit_error` maps to `provider_rate_limit`.
- graph-engine §6: the token events emitted before a failure stand, followed by the terminal failure event.

**Cases:**

1. `rate_limit_error_event_after_two_deltas`: content events `"Hel"` and `"lo"`, then `provider_rate_limit`.
2. `error_event_followed_by_message_stop_still_raises`: the same error followed by `content_block_stop`,
   `message_delta` and `message_stop` still raises `provider_rate_limit`.
3. `unlisted_error_type_maps_to_unavailable`: an `error.type` §8.2.3 does not list raises
   `provider_unavailable`, after one content event. A `text_delta` and a normal ending through `message_stop`
   follow the error. The category comes from the error event and not from the truncation rule, and the delta
   after the error emits no token event.

**What passes:**

- The token events before the error, then the raised category.

**What fails:**

- Returning a `Response`, with `finish_reason: "error"` or with the partial text.
- Ignoring the error event because `message_stop` followed it.
- Mapping every in-stream error to one category, or an unlisted type to anything but `provider_unavailable`.
- Dropping the token events emitted before the error.
- A token event for the `text_delta` that follows the error in case 3.

**Limits.** The terminal failure event itself is graph-engine's to assert; this fixture checks the raised
category and the token events.
