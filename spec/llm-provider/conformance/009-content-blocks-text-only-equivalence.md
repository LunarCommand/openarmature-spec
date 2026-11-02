# 009 — Content Blocks Text-Only Equivalence

A user message constructed with `content: "hello"` (string form) and a
user message constructed with `content: [TextBlock(text="hello")]`
(single-block content-array form) are normatively equivalent per §3.1.1.
The harness exercises both shapes via two sequential calls and asserts
that the responses are identical and that each call's wire content takes
the form §8.1.1 maps it to.

**Spec sections exercised:**

- §3 Message shape — user `content` MAY be a string OR a content-block
  sequence.
- §3.1.1 Text block — "A user message containing exactly one text block
  with text `T` is normatively equivalent to a user message with
  `content: T`."

**What passes:**

- Both calls produce identical `Response.message.content == "ack"` and
  `finish_reason: stop`.
- The outbound wire content for call 1 is the string `"hello"`.
- The outbound wire content for call 2 is the single-element content
  array `[{type: "text", text: "hello"}]`: §8.1.1 maps a content-block
  sequence to OpenAI's content-array form.

**What fails:**

- Either call raises (the two shapes MUST both be valid).
- The two calls produce different responses (the mock returns the same
  body for both).
- Call 2's wire content is collapsed to the string `"hello"`.
