# 077 — managed-field collision, clause (b): extras `stream` vs the always-determined mode

Pins the **always-managed** declared-field realization of llm-provider §6 clause (b) (proposal 0108) — OpenAI's
`stream`, the wire realization of the declared `complete(stream=…)` argument. Because the call *always* fixes a
stream mode, `stream` has **no declared-field-absent branch**: it is managed on both the streaming and unary
sides. This is the distinction from fixture 073's `stream_options`, which is *conditionally* managed (unmanaged,
riding untouched, on a non-streaming call). A matching extras `stream` is a no-op; a conflicting one — in either
direction — is rejected pre-send.

**Spec sections exercised:**

- llm-provider §6 — *Managed-field collision* clause (b): a declared field whose value is always determined (a
  mode switch) is always managed; matching no-op, conflicting reject pre-send.
- llm-provider §8.1.6 — `stream` is the wire realization of `complete(stream=…)`, an always-managed non-additive
  field; contrast the conditionally-managed `stream_options`.
- llm-provider §7 — `provider_invalid_request` at pre-send validation, no request issued.

**Cases:**

1. `streaming_call_conflicting_extras_stream_false_rejected_pre_send` — `complete(stream=True, config={extras:
   {stream: false}})` → conflict → reject pre-send, no request, no token events.
2. `unary_call_conflicting_extras_stream_true_rejected_pre_send` — `complete(config={extras: {stream: true}})`
   unary → conflict → reject pre-send (proves `stream` is managed on the unary side too, where `stream_options`
   would ride untouched).
3. `unary_call_matching_extras_stream_false_is_no_op` — `complete(config={extras: {stream: false}})` unary →
   matching no-op; the wire carries **no** `stream` key (the extras is absorbed, not forwarded).

**What fails:**

- Treating `stream` as conditionally managed (letting an extras `stream` ride untouched on a unary call, as
  `stream_options` does), letting a conflicting value flip the mode, forwarding the matching value onto the wire,
  or issuing a request on either reject case.
