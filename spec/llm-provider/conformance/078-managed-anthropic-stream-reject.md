# 078 — §8.2 Anthropic manages the body `stream` field (extras-`stream` reject)

Pins the fix for the consumer-break smuggling path: §8.2 Anthropic consumes an **atomic** response and does not
realize a declared `stream` (streaming is unimplemented; §5 rejects a declared stream-set call). But Anthropic's
Messages API accepts a body `stream` flag, so an extras `stream: true` on a **non-**stream-set call — which §5
does not catch (the declared param is unset) — would ride the §6 untouched pass-through onto the wire, make
Anthropic stream, and break the atomic consumer. §8.2 therefore **manages** `stream` for its consumer's
correctness: an extras `stream` selecting streaming is rejected pre-send (same outcome as §5's declared-stream
rejection); a matching `stream: false` is a no-op.

**Spec sections exercised:**

- llm-provider §6 clause (b) / §8.2 — a mapping manages a wire key whose colliding extras value would break its
  own consumer, even when it does not realize the declared field.
- llm-provider §5 — a non-streaming mapping MUST NOT silently fall back to a streamed response.
- llm-provider §7 — `provider_invalid_request` at pre-send validation, no request issued.

**Cases:**

1. `extras_stream_true_on_atomic_mapping_rejected_pre_send` — `complete(config={max_tokens: 64, extras: {stream:
   true}})` unary → reject pre-send, no request issued (§5 does not fire because the *declared* stream param is
   unset; §8.2's managed `stream` catches the extras value).
2. `extras_stream_false_on_atomic_mapping_no_op` — matching `stream: false` → no-op, wire carries no `stream` key.

**What fails:**

- Forwarding an extras `stream: true` untouched to the Anthropic wire (the consumer break), or issuing any request
  on the reject case, or treating `stream` as unmanaged because §8.2 does not realize a declared `stream`.
