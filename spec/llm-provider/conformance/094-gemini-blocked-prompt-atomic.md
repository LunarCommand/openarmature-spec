# 094: A Blocked Gemini Prompt Returns an Empty `content_filter` Response

Verifies llm-provider §8.3.2's blocked-prompt rule (proposal 0128) on an atomic call. Gemini answers a prompt
it blocks with HTTP 200, `promptFeedback.blockReason` and no candidates. The mapping returns a `Response`
rather than raising.

**Spec sections exercised:**

- llm-provider §8.3.2 *Blocked prompt*.
- llm-provider §3 *An empty response*: empty content is allowed for `"content_filter"`, and the empty string
  is its form.
- llm-provider §8.3.2's usage rule and §6: a counter the provider does not report is `null`.

**What passes:**

- `message.content` is `""`, with no tool calls.
- `finish_reason` is `"content_filter"`.
- `usage` has `prompt_tokens` 9, `total_tokens` 9 and `completion_tokens` `null`.
- `raw` keeps `promptFeedback`, `usageMetadata`, `modelVersion` and `responseId` as received.

**What fails:**

- `provider_invalid_response` because there is no candidate.
- An empty block list, or `null`, as the content.
- `completion_tokens` 0, or all three counters `null`.
- `promptFeedback` missing from `raw`.

Fixture 095 is the same blocked prompt streamed.
