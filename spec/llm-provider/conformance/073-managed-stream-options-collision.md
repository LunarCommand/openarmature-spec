# 073 — managed-field collision, reject arm: extras `stream_options` vs the mapping's usage-collection flag

The second llm-provider managed-field-collision fixture (with 072). Per §8.1.6, while streaming the OpenAI
mapping sets `stream: true` plus `stream_options: {include_usage: true}` so the terminal chunk carries usage
(OpenAI omits usage from streamed responses otherwise), and its §6 *Streaming assembly* consumer depends on
that usage. So `stream_options` is a **conditionally-managed** field — managed while streaming.

**Spec sections exercised:**

- llm-provider §6 — *Managed-field collision* (reject arm), conditionally-managed variant.
- llm-provider §8.1.6 — the streaming request sets `stream: true` + `stream_options: {include_usage: true}`;
  neither is sent for a non-streaming call.
- llm-provider §7 — `provider_invalid_request` raised at pre-send validation, no request issued.

**Cases:**

1. `extras_stream_options_conflicts_rejected_pre_send` — `complete(stream=True, config={extras: {stream_options:
   {include_usage: false}}})`. The extras `stream_options` collides with the mapping's `{include_usage: true}`;
   `include_usage: false` would drop the terminal-chunk usage the mapping reads, silently breaking
   `Response.usage`. The mapping raises `provider_invalid_request` pre-send, issues **no** request, emits no
   `LlmTokenEvent`, and neither drops nor forwards the value.
2. `extras_stream_options_without_streaming_rides_untouched` — `complete(config={extras: {stream_options:
   {include_usage: false}}})` **non-streaming**. The mapping sends no `stream` / `stream_options`, so the field
   is **unmanaged**: the extras value rides untouched onto the wire — the mapping does not manage it when not
   streaming (whether the backend accepts the stray key is caller-beware per §6; OpenAI itself requires
   `stream_options` only with `stream: true`) — the atomic call proceeds normally. Proves `stream_options` is
   **conditionally** managed.

**What fails:**

- Forwarding a conflicting `stream_options` onto the wire while streaming (breaking usage collection), or
  silently dropping it — case 1.
- Rejecting the extras `stream_options` for a non-streaming call, or omitting it from the wire — case 2.
