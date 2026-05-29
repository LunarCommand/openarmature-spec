# 052 — Gemini thought-signature round-trip

Verifies §8.3.2 thought-signature capture and §8.3.1.1 reattachment: a `thought: true` summary maps
to `ThinkingBlock.text` (no own signature), a `functionCall` part's `thoughtSignature` maps to
`ToolCall.signature`, and the signature reattaches in position on round-trip.

**Spec sections exercised:**

- §8.3.2 — a `thought: true` summary part → `ThinkingBlock.text` (the summary carries no signature);
  a `thoughtSignature` on a `functionCall` part → `ToolCall.signature`.
- §8.3.1.1 — on send, `ThinkingBlock` → `{text, thought: true}`; `ToolCall.signature` reattaches as
  `thoughtSignature` on the `functionCall` part, in original position.
- §3.1.4 — `ThinkingBlock.signature` may be absent (Gemini's summary part carries none).

**What passes:**

- Call 1: the thought summary surfaces as a `ThinkingBlock` with no signature; the signed
  `functionCall` surfaces as a `ToolCall` carrying `signature: "sig-g1"`.
- Call 2: the wire request reattaches `thoughtSignature: "sig-g1"` to the `functionCall` part, and
  the thought summary re-emits as `{text, thought: true}` with no `thoughtSignature`.

**What fails:**

- The `thoughtSignature` attached to the thought-summary part instead of the `functionCall` part.
- The signature dropped on round-trip (not reattached in position).
- `finish_reason` reported as `"stop"` instead of `"tool_calls"` when a `functionCall` is present.
