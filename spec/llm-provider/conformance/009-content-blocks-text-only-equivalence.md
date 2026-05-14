# 009 — Content Blocks Text-Only Equivalence

A user message constructed with `content: "hello"` (string form) and a
user message constructed with `content: [TextBlock(text="hello")]`
(single-block content-array form) are normatively equivalent per §3.1.1.
The harness exercises both shapes via two sequential calls and asserts
the response is identical and that the wire content is semantically
equivalent.

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
- The outbound wire content for call 2 is either the string `"hello"`
  (implementations MAY collapse single-TextBlock to string form) OR the
  single-element content array `[{type: "text", text: "hello"}]`. Both
  are semantically equivalent per §3.1.1.

**What fails:**

- Either call raises (the two shapes MUST both be valid).
- The two calls produce different responses (the mock returns the same
  body for both).
