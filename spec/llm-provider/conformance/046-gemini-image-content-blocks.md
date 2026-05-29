# 046 — Gemini image content blocks

Verifies §8.3.1.1 image-block wire mapping: inline → `inlineData`, URL → `fileData`, `detail`
dropped.

**Spec sections exercised:**

- §8.3.1.1 — an inline `ImageBlock` maps to `{inlineData: {mimeType, data}}`; a URL `ImageBlock`
  maps to `{fileData: {mimeType, fileUri}}`.
- §3.1.2 — the `detail` hint is dropped (Gemini does not honor it).

**What passes:**

- The inline image's `media_type` → `inlineData.mimeType`; `base64_data` → `inlineData.data`,
  passed through verbatim.
- The URL image's URL → `fileData.fileUri` (mimeType inferred from the URL).
- The `detail: "high"` hint is absent from the wire request.

**What fails:**

- Inline image bytes re-encoded or transcoded instead of passed through verbatim.
- The `detail` hint emitted on the wire.
- A URL image emitted as `inlineData` (or an inline image emitted as `fileData`).
