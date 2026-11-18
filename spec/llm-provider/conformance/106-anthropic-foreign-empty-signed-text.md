# 106: Anthropic Drops a Foreign Empty Signed Text Block

Verifies llm-provider §3.1.7 and §8.2.1.1 (proposal 0128). Gemini can deliver a thought signature on a text
part with empty text, which maps to an empty signed `TextBlock` (§3.1.1). Anthropic signs no text blocks, so
a signed `TextBlock` sent to the §8.2 mapping comes from another provider's history. The mapping strips its
signature. An empty block left with nothing is dropped, not rejected. A signed non-empty block keeps its
text. A message that the strip leaves with no content and no tool calls is rejected before sending.

**Spec sections exercised:**

- llm-provider §3.1.7: stripping the signature from an empty signed block drops the block; a message left
  empty is rejected with `provider_invalid_request`.
- llm-provider §8.2.1.1: a foreign empty signed text block is stripped and dropped.

**Cases:**

1. `empty_signed_text_block_dropped_signed_text_stripped`: the wire assistant message holds only
   `{type: text, text: "Result ready."}`, with no signature and no empty block.
2. `message_left_empty_by_strip_rejected_pre_send`: an assistant message holding only the empty signed block
   raises `provider_invalid_request`, and no request is sent.

**What passes:**

- Case 1's wire request as stated, and the ordinary `Response`.
- Case 2 raises before sending.

**What fails:**

- Sending `{type: text, text: ""}`, which Anthropic rejects, or rejecting case 1's call because of the empty
  block.
- Sending a signature on a text block.
- Sending an assistant turn with empty content in case 2, or dropping the message silently.
