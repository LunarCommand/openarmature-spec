# 011 — Content Blocks Image Inline Base64

User message with one inline-base64 `ImageBlock` followed by one `TextBlock`.
Verifies §8.1.1's mapping for the inline image variant — the spec block's
`media_type` and inline `base64_data` get composed into a single `data:`
URL on the wire per RFC 2397.

**Spec sections exercised:**

- §3.1.2 Image block — `media_type` field on the block; required when
  `source` is `inline`.
- §3.1.3 Image source — `inline` variant: `{ type: "inline", base64_data: <string> }`.
- §8.1.1 Content-block wire mapping — inline-source image block →
  `{ "type": "image_url", "image_url": { "url": "data:<media_type>;base64,<base64_data>" } }`.

**What passes:**

- The outbound wire payload's image entry has
  `image_url.url == "data:image/jpeg;base64,ABC123=="`.
- The text block follows the image block in array order.

**What fails:**

- The data URI is malformed — would mean the implementation isn't
  constructing per RFC 2397.
- `media_type` is read from the wrong location (e.g., from `source.media_type`
  instead of from the block) — would mean §3.1.2/§3.1.3 distinction was
  ignored.
- The bytes are transcoded or re-encoded — §3.1.3 forbids transformation.
