# 014 — LLM Payload Truncation

Verifies the §5.5.5 truncation contract for the `openarmature.llm.input.messages` attribute when
the serialized value exceeds the default 64 KiB per-attribute byte cap.

**Spec sections exercised:**

- §5.5.5 per-attribute byte cap — default 65,536 bytes (64 KiB) per payload attribute.
- §5.5.5 truncation algorithm — five-step procedure producing an attribute that ends with the
  marker `…[truncated, M bytes total]` where M is the pre-truncation byte length.
- §5.5.5 UTF-8 boundary safety — truncation backtracks to the nearest UTF-8 code-point boundary
  so multi-byte sequences are not split.

**Cases:**

1. `truncation_default_cap` — single user message containing ~100 KiB of content. Observer has
   `disable_llm_payload = False` and the default 64 KiB cap. The emitted
   `openarmature.llm.input.messages` is at most 64 KiB, ends with the marker pattern, and the
   bytes preceding the marker form a valid prefix of the full (untruncated) serialization.

**Harness extensions:**

- `content_repeat` — synthesizes a repeated-character message content of a specified byte count
  (e.g., 100 KiB of `"x"`). Implementations expand this into a single user message with that
  content before dispatching.
- `attribute_truncation` — mapping of attribute name → truncation assertions:
  - `max_bytes`: integer; attribute UTF-8 byte length MUST be ≤ this value.
  - `marker_pattern`: regex; attribute MUST end with a string matching this pattern (Unicode
    ellipsis U+2026 followed by `[truncated, N bytes total]` with N a decimal integer).
  - `utf8_valid`: boolean; the attribute MUST decode as valid UTF-8 in full (no split multi-byte
    sequences).
  - `prefix_of_full_serialization`: boolean; the bytes preceding the marker MUST be a prefix of
    the untruncated serialization the implementation would have produced for the same input.

**What passes:**

- Attribute byte length ≤ 65,536.
- Attribute ends with `…[truncated, N bytes total]` (N is the pre-truncation byte length).
- Attribute decodes as valid UTF-8 (no split code points).
- Bytes preceding the marker are a prefix of the full serialization.

**What fails:**

- Attribute exceeds 64 KiB → implementation did not enforce the cap.
- Attribute decodes invalid UTF-8 (split multi-byte sequence) → implementation did not backtrack
  to a code-point boundary.
- Marker is absent or in the wrong shape → implementation emitted truncated content without the
  signal byte sequence.
- Bytes preceding the marker do not form a prefix of the full serialization → truncation
  reordered or modified content rather than emitting the first N' bytes.
