# 033 — Anthropic basic message round-trip

Verifies the §8.2 Anthropic Messages mapping's fundamental request/response shape: system
extraction, the user/assistant-only `messages` array, `max_tokens` on the wire, and response
parsing into a §6 `Response`.

**Spec sections exercised:**

- §8.2.1 — system extraction to the top-level `system` field; `max_tokens` mapping.
- §8.2.1 message body shape — spec `system` message removed from `messages`; spec `user` maps to
  Anthropic `user`.
- §8.2.2 — response mapping (content text → `Response.message`, `stop_reason: end_turn` → `"stop"`,
  usage `input_tokens`/`output_tokens` → `prompt_tokens`/`completion_tokens`).

**Harness extension:** `mapping: anthropic` selects the §8.2 mapping (fixtures without it target
§8.1 OpenAI).

**What passes:**

- The wire request carries `system: "You are helpful."` as a top-level field, NOT a `messages`
  entry; the `messages` array contains only the user turn.
- `max_tokens: 256` is on the wire.
- The response maps to `finish_reason: "stop"` (from `end_turn`), text content, and usage
  `{prompt_tokens: 12, completion_tokens: 3, total_tokens: 15}`.

**What fails:**

- The system message appears in the `messages` array rather than the top-level `system` field.
- `max_tokens` is absent from the wire.
- `end_turn` is not mapped to `"stop"`, or usage is not mapped from `input_tokens`/`output_tokens`.
