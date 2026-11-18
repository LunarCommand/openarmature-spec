# 089: A Gemini Error Chunk Inside a Stream Raises by §8.3.3

Verifies llm-provider §8.3.6 and §8.3.3 (proposal 0128). A chunk that carries an `error` object, in a
stream that began with HTTP 200, ends the call. The mapping maps it on its `code` and `status`, as the HTTP response with that
error would map, and the call raises. Token events already emitted stand.

The cases also pin §8.3.3's precedence between its code and status rows, for an error that does not match the content-part
row (fixture 049 covers that row). A row whose code and status both match decides. Otherwise the code decides, a row matching only the status decides when the code is not listed,
and when neither is listed the error maps to `provider_unavailable`.

**Spec sections exercised:**

- llm-provider §8.3.6 *Errors*: an in-stream `error` chunk maps by §8.3.3 and ends the call.
- llm-provider §8.3.3 *Precedence*.
- llm-provider §6 *Streaming assembly* and graph-engine §6: token events emitted before the error stand.

**Cases:**

1. `rate_limit_error_chunk_after_text_raises`: one text part, then `{code: 429, status:
   "RESOURCE_EXHAUSTED"}`. One content token event, then `provider_rate_limit`.
2. `listed_code_with_unlisted_status_decides_by_code`: `{code: 400, status: "FAILED_PRECONDITION"}` raises
   `provider_invalid_request`.
3. `unlisted_code_and_status_fall_back_to_unavailable`: `{code: 409, status: "ABORTED"}` raises
   `provider_unavailable`. A normal chunk with `finishReason: STOP` follows the error, so the category comes
   from the error chunk and not from the truncation rule, and the error ends the call although chunks follow.

**What passes:**

- Case 1 emits exactly the one content token event and raises `provider_rate_limit`.
- Cases 2 and 3 emit no token events and raise the categories above.

**What fails:**

- The error chunk ignored, so the stream ends with no finish reason or is returned as a `Response`.
- The emitted token event withdrawn or not delivered when the call raises.
- Case 2 decided by status, falling to `provider_unavailable`.
- Case 3 raising anything other than `provider_unavailable`, such as an uncategorized error, or returning a
  `Response` because a chunk with a finish reason followed the error.
- Case 3 emitting a token event for the text in the chunk after the error.
