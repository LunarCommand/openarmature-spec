# 044 — Gemini basic message round-trip

Verifies §8.3.1 system extraction, the `assistant`↔`model` role rename, and the `contents` /
`parts` request shape.

**Spec sections exercised:**

- §8.3.1 — `system` messages are extracted to the top-level `systemInstruction` `Content`; the
  `contents` array carries only `user` / `model` entries.
- §8.3.1.1 — a user text message maps to a `{text: ...}` part.
- §8.3.2 — `candidates[0].content` (role `model`) maps back to a spec `assistant` message;
  `finishReason: STOP` → `finish_reason: "stop"`.

**What passes:**

- The system message becomes `systemInstruction.parts[].text`, not a `contents` entry.
- The user message maps to a `user`-role `Content` with a text part.
- `max_tokens` maps under `generationConfig.maxOutputTokens`.
- The `model`-role response maps back to a spec `assistant` message.

**What fails:**

- The system message emitted as a `contents` entry (Gemini has no `system` role).
- The assistant response surfaced with role `model` instead of `assistant`.
- `max_tokens` emitted at the request root instead of under `generationConfig`.
