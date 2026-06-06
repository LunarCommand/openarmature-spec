# 004 — Multimodal user message (§3)

A user sends a `ChatMessage` with mixed text + image content blocks per
llm-provider §3.1's content-block model. The chat harness accepts the
canonical content-block shape unchanged; the message threads through the
graph and into history.

**Spec sections exercised:**

- harness-chat §3 — `ChatMessage` shape with `content: list[ContentBlock]`
- llm-provider §3.1 — content-block types (text, image)

**What passes:**

- `send()` accepts the multimodal `ChatMessage` without validation error.
- The user message in final state's history preserves both content blocks
  (text + image) with the exact field shape per llm-provider §3.1.
- The assistant reply appends to history; final count is 2.

**What fails:**

- The chat harness rejects multimodal content — would mean §3 is requiring
  a string-only `content` shape contrary to llm-provider §3's allowance.
- The image block is stored with a divergent shape (e.g., flattened
  `image_url` field instead of the §3.1.3 `source: {type, url}` record) —
  would mean the canonical content-block shape isn't being preserved.
