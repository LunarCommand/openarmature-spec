# 035 — Anthropic image content blocks

Verifies the §8.2.1.1 image-block wire mapping for both source variants.

**Spec sections exercised:**

- §8.2.1.1 — `ImageBlock` inline source → `{type: image, source: {type: base64, media_type,
  data}}`; URL source → `{type: image, source: {type: url, url}}`.
- §8.2.1.1 — the `detail` hint is dropped (Anthropic does not honor it).

**What passes:**

- The inline image maps to a `base64` source carrying `media_type` and `data`; the `detail: high`
  hint does not appear on the wire.
- The URL image maps to a `url` source.
- Block order (image, image, text) is preserved.

**What fails:**

- The inline image emitted with OpenAI's `image_url` / `data:` URI shape instead of Anthropic's
  `base64` source.
- The `detail` hint forwarded to the wire (Anthropic rejects unknown fields).
- Block order not preserved.
