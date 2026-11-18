# 099: A Truncated Gemini Stream Raises `provider_unavailable`

Verifies llm-provider §8.3.6 *Errors* (proposal 0128). A stream that ends with no chunk carrying a
`finishReason` or a `promptFeedback.blockReason` is a connection error, `provider_unavailable`. The token
events already emitted stand, and the call raises.

**Spec sections exercised:**

- llm-provider §8.3.6 *Errors*: the truncation rule.
- llm-provider §6 *Streaming assembly* and graph-engine §6: token events emitted before the failure stand.

**What passes:**

- One content token event, `"Once upon"`, then `provider_unavailable`.

**What fails:**

- A `Response` built from the partial text, with any finish reason.
- `provider_invalid_response` in place of `provider_unavailable`.
- The emitted token event not delivered.
