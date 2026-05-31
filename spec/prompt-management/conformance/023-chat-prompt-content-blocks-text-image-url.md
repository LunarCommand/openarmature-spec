# 023 — Chat-Prompt Content-Blocks Render (Text + Image-URL)

Verifies §3.1 content-blocks template rendering and §6.render content-blocks segment rule
for the canonical multimodal user-message-with-image case: a user segment carrying a text
block + a URL-source image block, each with variable substitution.

**Spec sections exercised:**

- §3.1 — content-blocks template; text block template; image block template (URL source).
- §6.render — content-blocks segment render rule; per-block variable substitution.
- §8 — per-block strict-undefined (positive case — all referenced variables supplied).
- llm-provider §3.1.1 (text block shape), §3.1.2 (image block shape), §3.1.3 (image
  source shapes).

**Cases:**

1. `content_blocks_text_image_url_render` — chat_template [system, user-with-blocks];
   user segment's content-blocks is [text block, image-URL block]. Render with variables
   substituting into both the text and the URL. Asserts the resulting messages has two
   entries; the user Message's content is a 2-block sequence with the substituted text
   and the substituted URL.

**Harness extensions:**

- Content-blocks content shape on a ChatSegment: `content: [<ContentBlockTemplate>, ...]`
  with `{type: "text", text: ...}` and `{type: "image", source: {type: "url", url: ...}}`
  block-template shapes.

**What passes:**

- `PromptResult.messages` has length 2.
- `messages[0]` is the system text Message.
- `messages[1]` is `{role: "user", content: [<text block>, <image-URL block>]}` — content
  is a block sequence, NOT a string.
- The text block has its template substituted (`Describe widget:`).
- The image block's `source` is `{type: "url", url: "https://example.com/widget.png"}` with
  the URL template substituted.

**What fails:**

- The user Message's content is a string (the rendered text concatenated, with the URL
  dropped or interpolated as text) — implementation flattened the block sequence into
  text. The §6.render content-blocks rule requires producing a block-sequence Message,
  not a text Message.
- Variable substitution didn't apply to the image block's `url` template — implementation
  only substituted into text-block content.
- The block order was reversed — implementations MUST preserve the authored block order
  (matches llm-provider §3.1.6's note that block order MAY be semantically meaningful).
- The system segment was lifted into a content-block on the user message — implementations
  MUST keep segments separate.
