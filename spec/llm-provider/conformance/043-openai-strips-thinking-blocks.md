# 043 — OpenAI strips thinking blocks (cross-provider interop)

Verifies the §8.1.1 strip-on-send rule: thinking blocks carried in an assistant message are
stripped when the message is routed through the §8.1 OpenAI mapping (which has no wire
representation for reasoning content).

**Spec sections exercised:**

- §8.1.1 strip-on-send — when an assistant message carries `ThinkingBlock` /
  `RedactedThinkingBlock` entries (e.g., conversation history that accrued them under a
  different provider's mapping), the §8.1 OpenAI mapping strips them before emitting the wire
  request, deterministically and without error.
- §3.1.4 — reasoning-block signatures are provider-bound; cross-provider routing strips them.

**Harness note:** no `mapping` key — this fixture targets the §8.1 OpenAI-compatible mapping (the
pre-0037 default).

**What passes:**

- The wire request's assistant message contains only the text content (`"42."`); the thinking
  block and its `sig-xyz` signature do not appear.
- No error is raised; the response maps normally.

**What fails:**

- The thinking block forwarded to the OpenAI wire (OpenAI rejects unrecognized content shapes).
- An error raised on encountering the thinking block (strip is deterministic and silent).
- The provider-bound signature forwarded to a provider that did not issue it.
