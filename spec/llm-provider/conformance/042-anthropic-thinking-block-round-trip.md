# 042 — Anthropic thinking-block round-trip

Verifies the §3.1.4 ThinkingBlock surfacing and the §8.2.1.1 thinking-block wire mapping across
a multi-turn round-trip.

**Spec sections exercised:**

- §8.2.1.1 — Anthropic `{type: thinking, thinking, signature}` ↔ spec `ThinkingBlock {text,
  signature}` (the wire `thinking` field maps to the spec `text` field; the signature passes
  through verbatim in both directions).
- §3.1.4 — thinking blocks surface on `Response.message.content` and are preserved verbatim when
  the assistant message is sent back in a subsequent call.
- §3 assistant per-role constraint — `assistant` content may be a content-block sequence
  containing thinking + text blocks.

**Cases (two sequential calls):**

1. The first response carries a `thinking` block (with `signature: "sig-abc"`) and a `text`
   block. Both surface on `Response.message.content`; the ThinkingBlock uses the spec `text`
   field.
2. The second call passes the assistant message (including the thinking block) back. The wire
   request reconstructs the Anthropic `thinking` field from the spec `text` field, preserves the
   signature, and keeps the block in its original position before the text block.

**What passes:**

- Call 1: `Response.message.content` is `[ThinkingBlock{text, signature}, TextBlock{text}]`.
- Call 2: the wire `messages` preserves the assistant `thinking` block with `signature: "sig-abc"`
  intact and ordered before the text block.

**What fails:**

- The thinking block dropped from the response, or its signature lost.
- On round-trip, the signature stripped or the block reordered after the text block (Anthropic's
  multi-turn protocol requires signatures intact and in position).
- The spec `text` field not mapped back to the wire `thinking` field.
