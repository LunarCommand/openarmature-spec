# 015 — LLM Payload Image Redaction

Verifies the §5.5.5 inline-image redaction rule: inline image source records are replaced with
the `inline_redacted` placeholder before JSON encoding the message list; `media_type` stays at
the image-block level per llm-provider §3.1.2; `detail` is preserved verbatim when present; no
base64 bytes appear in the emitted attribute.

**Spec sections exercised:**

- §5.5.5 inline-image redaction rule — the `source` of an inline image is replaced with
  `{type: "inline_redacted", byte_count: N}` before JSON encoding.
- llm-provider §3.1.2 image-block shape — `media_type` lives on the image block, not inside
  `source`.

**Cases:**

1. `inline_image_redacted` — user message with one text block and one inline-image block
   (`image/png`, ~4 KiB of synthesized base64 data). `disable_provider_payload = False`. The emitted
   `openarmature.llm.input.messages` parses to a message list where the image block has its
   `source` replaced with the redacted placeholder carrying `byte_count: 4096`, while
   `media_type` and `detail` are preserved at the image-block level.

**Harness extensions:**

- `base64_data_synthetic` — synthesizes a base64 blob of specified byte length. The actual bytes
  are deterministic so the harness can recognize them later when checking absence.
- `attribute_does_not_contain` — assertion that a forbidden substring does NOT appear in an
  attribute value. The `forbidden_substring_kind: synthetic_base64_prefix` shape names a known
  fixture-side blob the harness can look up to derive the substring.

**What passes:**

- `openarmature.llm.input.messages` parses to a message list with the image block carrying
  `source: {type: "inline_redacted", byte_count: 4096}`, `media_type: "image/png"`, and
  `detail: "auto"`.
- The synthesized base64 data does not appear anywhere in the attribute string.

**What fails:**

- The attribute contains the synthesized base64 data — implementation did not redact.
- `media_type` is moved inside `source` rather than staying at the image-block level —
  implementation diverges from llm-provider §3.1.2.
- `detail` is dropped — implementation over-redacted.
- The redacted source carries `media_type` (the §5.5.5 spec puts `media_type` only at the block
  level; the redacted `source` carries just `type` and `byte_count`).
