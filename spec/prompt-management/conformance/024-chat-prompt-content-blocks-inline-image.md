# 024 — Chat-Prompt Content-Blocks Render (Inline Image)

Verifies §3.1 inline-source image block template rendering — both `base64_data` and
`media_type` are per-block templates, so a caller can supply pre-encoded image bytes and
the media type as variables at render time.

**Spec sections exercised:**

- §3.1 — image block template (inline source); both `base64_data` and `media_type` are
  templates.
- §6.render — per-block variable substitution into `base64_data` and `media_type`.
- llm-provider §3.1.2 / §3.1.3 — image block with inline source.

**Cases:**

1. `content_blocks_inline_image_render` — chat_template with one user segment whose
   content-blocks is a single inline-source image block. Render with `img_b64` and
   `img_media_type` variables. Asserts the resulting Message has a 1-block content
   sequence with the substituted inline source.

**Harness extensions:**

- Inline image block template shape: `{type: "image", source: {type: "inline",
  base64_data: <template>}, media_type: <template>}`.

**What passes:**

- `PromptResult.messages` has length 1.
- The Message's content is a 1-block sequence containing one image block with
  `source.type = "inline"`, `source.base64_data` = the substituted base64 string, and
  `media_type` = the substituted media type.

**What fails:**

- Variable substitution didn't apply to `base64_data` — the rendered block carries the
  literal `"{{ img_b64 }}"` string. Implementations MUST substitute into per-block
  template fields per §6.render.
- Variable substitution didn't apply to `media_type` — same issue. The §3.1 spec lists
  `media_type` as a template for inline-source blocks (distinct from URL-source where
  `media_type` is literal).
- The `detail` field (omitted in the fixture, default per llm-provider §3.1.2 / §3.1.3)
  was synthesized into something other than the spec default — implementations MUST NOT
  invent values for omitted optional fields.
- The image block was downgraded to a text block carrying the base64 string as its `text`
  field — implementations MUST preserve the image block type from the template.
