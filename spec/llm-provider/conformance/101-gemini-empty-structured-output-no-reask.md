# 101: An Empty Filtered Structured-Output Response Is Not Re-Asked

Verifies llm-provider §7.1 (proposal 0128), with §3 *An empty response* and §8.3.2. A Gemini response filtered
before it produced anything has content `""` and `finish_reason` `"content_filter"`. On a call with a
`response_schema` the empty content does not parse, so the call raises `structured_output_invalid` with
`output_content` `""`.

Such a failure is not re-asked even when `reask` is supplied. The re-ask appends the failed output as an
`assistant` turn, an empty one is invalid in a request (§3), and the loop has no other turn to append. The
builder is not invoked, and the error is handled as it would be without `reask`.

**Spec sections exercised:**

- llm-provider §7.1 *reask*: the empty-`output_content` rule.
- llm-provider §7: the `structured_output_invalid` surface, through conformance-adapter §5.12 and §5.13.
- llm-provider §3 *An empty response* and §8.3.2.

**Cases:**

1. `empty_filtered_response_raises_structured_output_invalid`: no retry. Raises `structured_output_invalid`
   with `output_content` `""`, `finish_reason` `"content_filter"` and usage 14, `null` and 14.
2. `empty_filtered_response_is_not_reasked`: a retry with `reask` and two attempts. One request on the wire,
   no appended messages, and the same error.

**What passes:**

- Both cases raise `structured_output_invalid` with the fields above.
- Case 2 sends exactly one request, and its second mock response is never consumed.

**What fails:**

- A second request carrying an empty `assistant` turn and the builder's correction.
- A second request rejected before sending with `provider_invalid_request`, which surfaces that category in
  place of `structured_output_invalid`.
- `output_content` `null` or absent in place of `""`.

**Limits.** The builder not being invoked is asserted as a named claim. One request on the wire, with no
appended messages, is what an implementation that skipped the re-ask but invoked the builder would also show.
