# 100: Empty Gemini Responses, Atomic

Verifies llm-provider §8.3.2 and §3 *An empty response* (proposal 0128). A Gemini candidate with no parts maps
to empty content, the empty string, when its `finishReason` maps to `"content_filter"`, `"length"` or
`"error"`. Under any other finish reason a response with no content and no tool calls is malformed and raises
`provider_invalid_response`.

**Spec sections exercised:**

- llm-provider §3 *An empty response*.
- llm-provider §8.3.2: a response with no content left, and the `finishReason` table.

**Cases:**

1. `safety_without_content_returns_empty_content_filter`: `SAFETY`, and the candidate has no `content` key.
   Returns `""` with `"content_filter"`.
2. `max_tokens_without_parts_returns_empty_length`: `MAX_TOKENS`, and the `content` has no `parts` key.
   Returns `""` with `"length"`.
3. `other_with_empty_parts_returns_empty_error`: `OTHER`, and `parts` is empty. Returns `""` with
   `"error"`.
4. `stop_without_parts_raises_invalid_response`: `STOP`, and `parts` is empty. Raises
   `provider_invalid_response`.

**What passes:**

- Cases 1 to 3 return content `""`, no tool calls, the mapped finish reason, and usage 9, `null` and 9, with
  `raw` as received.
- Case 4 raises `provider_invalid_response`.

**What fails:**

- An empty block list, or `null`, as the content in cases 1 to 3.
- `provider_invalid_response` in cases 1 to 3, for example from treating a missing `content` or `parts` key as
  unparseable.
- Case 4 returning a `Response`.

**Limits.** Each case's `usageMetadata` omits `candidatesTokenCount`, so `completion_tokens` is `null`.
