# 104: Gemini Sends Signed Empty Blocks Back and Rejects Unsigned Ones

Verifies llm-provider §8.3.1.1 with §3.1.1 and §3.1.4 (proposal 0128) on the request side. An empty block is
valid when it carries a signature, and the mapping sends it back on the part it came from. An empty text block
with no signature is still invalid and is rejected before sending.

**Spec sections exercised:**

- llm-provider §8.3.1.1: the signed `TextBlock` row, the signed `ThinkingBlock` row, and the empty-block
  rejection with its signed exemption.
- llm-provider §3.1.1 and §3.1.4: empty text when a signature is present.

**Cases:**

1. `empty_signed_text_block_sent_with_signature`: `{type: text, text: "", signature: "sig-e"}` is sent as
   `{text: "", thoughtSignature: "sig-e"}`, after the turn's other text part.
2. `signed_thinking_blocks_sent_as_signed_thought_parts`: an empty and a non-empty signed `ThinkingBlock` are
   each sent as `{text, thought: true, thoughtSignature}`.
3. `unsigned_empty_text_block_rejected_pre_send`: an empty `TextBlock` with no signature raises
   `provider_invalid_request`, and no request is sent.

**What passes:**

- Cases 1 and 2 send the exact bodies shown, each signature on its own part, and return the mock's
  `Response`.
- Case 3 raises `provider_invalid_request` with no request on the wire.

**What fails:**

- The empty signed block rejected, or dropped from the wire.
- A signed `ThinkingBlock` sent without `thought: true`, or its signature moved to a sibling part.
- `thoughtSignature` emitted as `null` or `""` on an unsigned part.
- Case 3 sending the empty block, or dropping it and sending the rest.
