# 053 — Cross-provider signature strip

Verifies §3.1.7 — reasoning-continuity signatures are provider-bound; routing a message carrying
Gemini-origin signatures through a different provider's mapping (here §8.1 OpenAI) strips them.

**Spec sections exercised:**

- §3.1.7 — `ThinkingBlock`, `TextBlock.signature`, and `ToolCall.signature` are provider-bound;
  on a cross-provider hop the mapping MUST strip the signatures and any thinking/redacted-thinking
  blocks before emitting the wire request, with no error.
- §8.1.1 — the OpenAI mapping has no wire slot for thinking blocks or signatures.

**What passes:**

- The Gemini-origin thinking block is stripped.
- The signed `TextBlock` loses its `signature`; the text survives (collapses to a string).
- The signed `ToolCall` loses its `signature`; the tool call itself survives in the OpenAI wire
  shape. No error is raised.

**What fails:**

- A `signature` / `thoughtSignature` field emitted on the OpenAI wire (which has no slot for it).
- The thinking block forwarded instead of stripped.
- An error raised on encountering the foreign signatures instead of stripping deterministically.
