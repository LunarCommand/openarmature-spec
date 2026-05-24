# 027 — Structured Output Prompt-Augmentation Fallback

Verifies §8.1.5.1: when the provider does not natively support
`response_format`, the implementation falls back to prompt augmentation.
The fallback constructs a *modified copy* of the message list with a
JSON-only system directive appended; sends without `response_format`;
parses and validates the response against `response_schema`
post-receive. The caller's original messages MUST NOT be mutated.

**Spec sections exercised:**

- §8.1.5.1 Fallback for providers without native structured output —
  prompt-augmentation strategy steps 1-4.
- §8.1.5.1 message-list mutation rule — the caller's original `messages`
  MUST be left unchanged (matching §5's mutation rule).
- §6 — `parsed` is still populated under the fallback path (validation
  happens post-receive).

**What passes:**

- Wire request does NOT include `response_format` (native path bypassed).
- Wire request includes a system directive referencing the schema or
  "JSON only" output requirement.
- After the call returns, the caller's original `messages` list is
  unchanged (no in-place mutation).
- `Response.parsed == {value: 42}` (post-receive validation succeeded).

**What fails:**

- `response_format` is included on the wire — would mean the fallback
  detection didn't fire even though the provider doesn't support it.
- No system directive is added — would mean the fallback didn't
  construct the augmented prompt.
- The caller's `messages` is mutated — violates §5/§8.1.5.1 mutation rule.
