# 054 — Wire-byte stability (OpenAI-compatible)

Verifies §8 *Intra-impl wire-byte stability* — two `complete()` calls whose OA inputs are
structurally equivalent but were constructed with different insertion / iteration orders MUST
produce byte-identical wire request bodies.

**Spec sections exercised:**

- §8 framing — *Intra-impl wire-byte stability* paragraph (sorted JSON object keys, recursive
  JSON Schema canonicalization, `RuntimeConfig` extras, content-block source dicts).
- §8.1.1 — OpenAI-compatible request mapping; *Wire-byte stability* sub-paragraph anchoring the
  rule to OpenAI-specific payloads (tool `parameters` schemas, request-body extras, content-block
  inline-image source dicts).

**What passes:**

- The two calls emit identical wire bytes despite their tool-parameter schemas being constructed
  with object-key insertion in different orders.
- The `RuntimeConfig` extras (an undeclared object) emit with sorted keys; the second call's
  alternate insertion order produces identical bytes.
- Content-block source dicts (an inline image with `{type, source, media_type, detail}`) emit
  with sorted keys regardless of source-side ordering.

**What fails:**

- The two wire bodies differ in any byte (key order, whitespace, number formatting, etc.).
- Implementation emits insertion-order or hash-set-order JSON.
