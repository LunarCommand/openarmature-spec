# 071 — Malformed usage counter on a streamed terminal chunk

Verifies the llm-provider §7 *Malformed usage counter* rule for a **streamed** completion. §6 *Streaming assembly* sources usage from the terminal chunk; §7 nulls a malformed counter on the normalized `Response.usage` exactly as for a non-streamed call. §6's streaming clause requires the terminal chunk's usage block to be preserved **verbatim** on the assembled `Response.raw`, so the corrupt value stays inspectable — the same transparency guarantee a non-streamed call has.

**Spec sections exercised:**

- llm-provider §7 *Malformed usage counter* — a malformed terminal-chunk `prompt_tokens` is nulled; the sound counters stand; no raise.
- llm-provider §6 *Streaming assembly* — usage sourced from the terminal chunk; the assembled `raw` preserves the terminal chunk's usage block verbatim.
- llm-provider §8.1.6 — OpenAI-compatible streaming wire path (`stream: true` + `stream_options.include_usage`, SSE `data:` chunks, the `[DONE]` sentinel). Expressed in the `cases:` / `call:` streaming dialect of fixture 059 (a case-nested `mock_provider.responses[].stream_body` + the `call.stream` directive) — the dialect the harness wires SSE into, so the call runs as a genuine streamed completion.

**Scenario:**

A `complete(stream=True)` call. The mock SSE stream yields one content chunk (`"Hi."`, `finish_reason: stop`), then a terminal empty-choices usage chunk carrying `{prompt_tokens: "abc", completion_tokens: 3, total_tokens: 10}`, then `[DONE]`.

**What passes:**

- The wire request carries `stream: true` and `stream_options: {include_usage: true}`.
- The assembled `Response.usage` is `{prompt_tokens: null, completion_tokens: 3, total_tokens: 10}` — the malformed terminal counter nulled, the sound counters standing.
- `finish_reason` is `stop`; `complete()` does not raise.
- The terminal chunk's usage block — including the malformed `"abc"` — survives verbatim on the assembled `raw`.

**What fails:**

- The malformed counter reaches the normalized `Response.usage` as anything other than `null` (coerced, clamped, repaired, or the whole record nulled).
- The assembled `raw` drops or normalizes the terminal chunk's usage block, so the verbatim `"abc"` is no longer inspectable.
- The implementation raises over the malformed terminal-chunk counter.
