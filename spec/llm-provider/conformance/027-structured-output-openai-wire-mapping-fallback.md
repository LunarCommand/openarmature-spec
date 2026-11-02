# 027 — Structured Output Prompt-Augmentation Fallback

Verifies §8.1.5.1: when the provider does not natively support
`response_format`, the implementation SHOULD fall back to prompt
augmentation. The fallback constructs a *modified copy* of the message
list with a JSON-only system directive appended; sends without
`response_format`; parses and validates the response against
`response_schema` post-receive. The caller's original messages MUST NOT
be mutated.

**Spec sections exercised:**

- §8.1.5.1 Fallback for providers without native structured output —
  prompt-augmentation strategy steps 1-4.
- §8.1.5.1 message-list mutation rule — the caller's original `messages`
  MUST be left unchanged (matching §5's mutation rule).
- §6 — `parsed` is still populated under the fallback path (validation
  happens post-receive).

**Cases:**

1. `prompt_augmentation_fallback`, gated on
   `llm_prompt_augmentation_fallback` (conformance-adapter §5.17), since
   §8.1.5.1 makes the fallback a SHOULD. The wire request carries the
   bound `model` and no `response_format`. Its messages are not asserted:
   §8.1.5.1 lets the directive be appended as a system message or merged
   into an existing one.
2. `response_holds_on_either_path`, ungated, on the same inputs. Without
   the fallback, the native request (§8.1.5) is the default and the
   mock's response is the same, so this case asserts what holds on either
   path: one request for the bound `model`, the response, its parsed
   value, and the caller's unmodified messages.

**What passes:**

- Case 1: the wire request does NOT include `response_format` (native
  path bypassed).
- After the call returns, the caller's original `messages` list is
  unchanged (no in-place mutation).
- `Response.parsed == {value: 42}` (post-receive validation succeeded).

**What fails:**

- Case 1: `response_format` is included on the wire. That would mean the
  fallback detection didn't fire even though the provider doesn't support
  it.
- The caller's `messages` is mutated — violates §5/§8.1.5.1 mutation rule.
