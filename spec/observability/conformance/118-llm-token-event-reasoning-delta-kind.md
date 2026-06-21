# 118 — `delta_kind="reasoning"` token events for streamed reasoning

Verifies graph-engine §6 and llm-provider §6 / §8.1.6: streamed reasoning deltas surface as `LlmTokenEvent(delta_kind="reasoning")`, emitted before the content deltas (`delta_kind="content"`). Reasoning assembles into the terminal `Response`'s reasoning / thinking block; content assembles into `message.content` (the `LlmCompletionEvent.output_content`). The reasoning-delta field name is an OpenAI-compatible extension that varies by backend, and the mapping MUST recognize both names → `delta_kind="reasoning"`.

**Spec sections exercised:**

- graph-engine §6 — `LlmTokenEvent.delta_kind` carries `"reasoning"` for streamed chain-of-thought text; forwarding observers route by kind.
- llm-provider §6 *Streaming assembly* — reasoning deltas assemble into the terminal `Response`'s thinking blocks AND emit live as `delta_kind="reasoning"`; content into `message.content`.
- llm-provider §8.1.6 — the OpenAI-compatible reasoning extension: `choices[].delta.reasoning_content` (DeepSeek / older vLLM) and `choices[].delta.reasoning` (current vLLM) both map to a reasoning delta; reasoning streams first, then content; the two are mutually exclusive within a chunk.

**Cases:**

1. `reasoning_content_field_yields_reasoning_kind_then_content` — Case A (DeepSeek-style). The mock yields two `reasoning_content` deltas then two `content` deltas. Asserts `chunk_index` `0,1` are `delta_kind="reasoning"` (`"Let me "`/`"think."`), `2,3` are `delta_kind="content"` (`"The answer "`/`"is 42."`), and the terminal `LlmCompletionEvent.output_content` is `"The answer is 42."` (content only).
2. `reasoning_field_yields_reasoning_kind_then_content` — Case B (current vLLM). Identical structure but reasoning arrives via `delta.reasoning`. Asserts the same ordered reasoning → content token-event sequence and the same content-only `output_content` — pinning that both field names produce identical `delta_kind="reasoning"` events.

**What passes:**

- Both `reasoning_content` (case A) and `reasoning` (case B) produce `LlmTokenEvent`s with `delta_kind="reasoning"`.
- Reasoning token events precede the content token events in `chunk_index` order.
- Reasoning assembles into the terminal `Response`'s thinking block; content into `message.content` / `output_content`.

**What fails:**

- A reasoning delta surfaced with `delta_kind="content"` (or not surfaced at all) under either field name.
- Reasoning leaking into `output_content` (the assembled content not being content-only).
- Content and reasoning token events interleaved out of the reasoning-first order.
