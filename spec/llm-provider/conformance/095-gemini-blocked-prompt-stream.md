# 095: A Blocked Gemini Prompt, Streamed

Verifies llm-provider §8.3.6 *Blocked prompt* (proposal 0128). A stream whose only chunk carries
`promptFeedback.blockReason` and no candidates is a blocked prompt. The call emits no token events and
returns the same `Response` as the atomic call in fixture 094.

**Spec sections exercised:**

- llm-provider §8.3.6 *Blocked prompt* and *Errors*: a stream ending with a `blockReason` is not a truncated
  stream.
- llm-provider §8.3.2 *Blocked prompt* and §3 *An empty response*.

**What passes:**

- `token_events` is empty.
- The `Response` has content `""`, no tool calls, `"content_filter"`, and usage 9, `null` and 9.
- `raw` holds the chunk's `promptFeedback` and `usageMetadata`.

**Not asserted:**

- `raw` has no `candidates` key. `raw_check` has no form for an absent key, so the fixture does not assert
  this; a reviewer checks it by hand. A merged response that adds `candidates: []` differs from the atomic
  response in fixture 094, whose `raw` is the body verbatim.

**What fails:**

- `provider_unavailable`, from reading a stream with no `finishReason` as truncated.
- `provider_invalid_response` because there is no candidate.
- A `Response` whose content, tool calls, finish reason or usage differs from fixture 094's, or whose `raw`
  lacks the `promptFeedback` or `usageMetadata` the chunk carried.
