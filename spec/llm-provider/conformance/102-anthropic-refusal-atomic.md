# 102: An Anthropic Refusal With No Content Maps to Empty `content_filter`

Verifies llm-provider §8.2.2 and §3 (proposal 0128), on an atomic response. A refusal can arrive with an empty
`content` array. `stop_reason: refusal` maps to `"content_filter"`, one of the three finish reasons for which
§3 allows empty content, so the message's content is the empty string. The refusal details stay on `raw`.

**Spec sections exercised:**

- llm-provider §3 *An empty response*: empty content is the empty string, not an empty block list.
- llm-provider §8.2.2: the empty-content rule, and `refusal` mapping to `"content_filter"` with
  `stop_details` kept on `raw`.

**Cases:**

1. `empty_refusal_maps_to_empty_content_filter`: the `Response` has `content: ""`, no tool calls,
   `"content_filter"` and usage 14, 0 and 14. `raw` keeps `content: []`, `stop_reason: refusal` and
   `stop_details`.

**What passes:**

- The empty-string content, the finish reason and usage, and the verbatim `raw` keys.

**What fails:**

- Raising `provider_invalid_response` because the message has no content and no tool calls.
- An empty block list as the content.
- Dropping `stop_details` from `raw`.
