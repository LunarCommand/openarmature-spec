# 010 — Content Blocks Image URL

User message with one URL-sourced `ImageBlock` followed by one `TextBlock`.
Verifies §8.1.1's OpenAI wire mapping for the URL image variant and the
§3.1.4 block-order preservation rule.

**Spec sections exercised:**

- §3.1.2 Image block — `type`, `source` fields.
- §3.1.3 Image source — `url` variant: `{ type: "url", url: <string> }`.
- §3.1.4 Mixing blocks — block order preserved through the wire.
- §8.1.1 Content-block wire mapping — URL-source image block →
  `{ "type": "image_url", "image_url": { "url": <url> } }`.

**What passes:**

- Outbound wire payload's user-message content is a 2-element array:
  `image_url` entry first (with the spec URL passed through unchanged),
  `text` entry second.
- Response surfaces the assistant's reply unchanged.

**What fails:**

- The wire payload is missing the image_url entry — would mean the URL-
  source variant isn't handled.
- The block order is swapped — would mean §3.1.4 ordering isn't preserved.
- The image URL is transformed (fetched, normalized, re-encoded) — would
  mean §3.1.3 "pass through to the wire unchanged" was violated.
