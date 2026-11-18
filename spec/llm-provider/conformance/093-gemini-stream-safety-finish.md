# 093: A Streamed Gemini Safety Stop Maps to `content_filter`

Verifies llm-provider §8.3.6 and §8.3.2 (proposal 0128). A stream whose last chunk carries
`finishReason: SAFETY` maps to `finish_reason` `"content_filter"`. The content token events emitted before
the stop stand, and the text produced before it is the message's content.

**Spec sections exercised:**

- llm-provider §8.3.6 *Assembly*: `finishReason` and the other `candidates[0]` fields take the last value any
  chunk carried.
- llm-provider §8.3.2: `SAFETY` maps to `"content_filter"`.
- llm-provider §6 *Streaming assembly*: content token events.

**What passes:**

- Two content token events, then a `Response` with `"The door opened"`, `"content_filter"` and usage 9, 3
  and 12.
- `raw.candidates` holds the joined text part, `SAFETY` and the last chunk's `safetyRatings`.

**What fails:**

- `finish_reason` `"stop"` or `"error"`.
- The call raising on a safety stop.
- The text before the stop discarded.
