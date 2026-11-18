# 086: Anthropic Streamed Thinking, and the Empty Signed Thinking Block

Verifies llm-provider §8.2.6, §3.1.4 and §8.2.1.1 (proposal 0128). A `thinking` block's text arrives as
`thinking_delta` events, each a reasoning token event, and its signature as a `signature_delta`. A
`redacted_thinking` block arrives whole and emits no event. With thinking display omitted, the block's text is
empty and it carries a signature: the mapping keeps it as an empty signed `ThinkingBlock`, emits no reasoning
event for it, and sends it back unchanged. An empty thinking block without a signature is still invalid.

**Spec sections exercised:**

- llm-provider §8.2.6: `thinking_delta`, `signature_delta`, a block that arrives whole, and the token events.
- llm-provider §6 *Streaming assembly*: an empty delta emits no token event.
- llm-provider §3.1.4: an empty thinking block is valid when signed, and is kept and sent back.
- llm-provider §8.2.1.1: the wire form of an empty signed thinking block, and the rejection of an unsigned
  empty one.

**Cases:**

1. `thinking_redacted_and_text_stream`: reasoning events `"Let me "` and `"work it out."`, then content events
   `"The answer "` and `"is 42."`, with `chunk_index` 0 to 3. The `Response` holds the signed `ThinkingBlock`,
   the `RedactedThinkingBlock` and the text block, in that order.
2. `display_omitted_gives_empty_signed_thinking_block`: an empty `thinking_delta` and a `signature_delta`
   give `{type: thinking, text: "", signature: "sig-086b"}` on the message. The only token event is the
   content event, at `chunk_index` 0.
3. `empty_signed_thinking_block_sent_back`: that message in history puts
   `{type: thinking, thinking: "", signature: "sig-086b"}` on the wire, before the text block.
4. `unsigned_empty_thinking_block_rejected_pre_send`: a thinking block with empty text and no signature is
   rejected with `provider_invalid_request`, and no request is sent.

**What passes:**

- The token events and blocks above, the empty signed block kept and sent back, and the pre-send rejection.

**What fails:**

- A token event for the redacted block or for the empty `thinking_delta`.
- Dropping the empty signed block, or rejecting the response as malformed because the block's text is empty.
- Sending the block back without its signature or with a placeholder text.
- Accepting an unsigned empty thinking block.
