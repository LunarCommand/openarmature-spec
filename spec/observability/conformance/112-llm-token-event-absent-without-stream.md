# 112 — No `LlmTokenEvent` without `stream` (backward-compat lockdown)

Verifies the opt-in gate for `LlmTokenEvent` (graph-engine §6, llm-provider §5): a `complete()` call without `stream` set emits zero `LlmTokenEvent`s and exactly one `LlmCompletionEvent`. The atomic path is unchanged by the streaming capability — token events fire only when a caller opts in.

**Spec sections exercised:**

- graph-engine §6 — `LlmTokenEvent` fires ONLY when the call was made with `stream` set; a non-streamed call emits no token events.
- llm-provider §5 — `stream` defaults to `False` / absent; the v0.4.0 atomic behavior is preserved exactly.

**Cases:**

1. `no_token_events_when_stream_unset` — The same single-LLM-node graph as fixture 111, invoked without `stream` (the atomic path), with a plain atomic mock response. Asserts zero `LlmTokenEvent`s and exactly one `LlmCompletionEvent`.

**What passes:**

- Zero `LlmTokenEvent`s observed.
- Exactly one `LlmCompletionEvent`, with the populated identity / outcome fields.

**What fails:**

- Any `LlmTokenEvent` emitted on a non-streamed call (token emission not gated on the flag).
- More or fewer than one `LlmCompletionEvent`.
