# 107: OpenAI Drops Foreign Empty Signed Blocks and Rejects Thinking-Only Turns

Verifies llm-provider §3.1.7, §8.1.1 and §8.1.1.1 (proposal 0128). The §8.1 mapping strips thinking blocks
and signatures before sending. An empty signed `TextBlock` from a Gemini history carries nothing once its
signature is gone, so it is dropped. A message that the strip leaves with no content and no tool calls would
be an assistant turn with no content, which §3 forbids, so the call is rejected before sending.

**Spec sections exercised:**

- llm-provider §3.1.7: an empty block whose signature is stripped is dropped; a message left empty is
  rejected with `provider_invalid_request`.
- llm-provider §8.1.1: strip-on-send raises no error unless it leaves the message empty.
- llm-provider §8.1.1.1: a signed empty text block from another provider is stripped and dropped.

**Cases:**

1. `empty_signed_text_block_dropped_signed_text_stripped`: fixture 106's history; the wire assistant message
   is `{role: assistant, content: "Result ready."}`.
2. `thinking_only_message_rejected_pre_send`: an assistant message holding only a `ThinkingBlock` raises
   `provider_invalid_request`, and no request is sent.
3. `redacted_thinking_only_message_rejected_pre_send`: the same with only a `RedactedThinkingBlock`.

**What passes:**

- Case 1's wire request as stated.
- Cases 2 and 3 raise before sending.

**What fails:**

- An empty string or an empty block left in case 1's assistant content, or a signature on the wire.
- Sending `content: ""` or `content: null` for the thinking-only messages in cases 2 and 3.
