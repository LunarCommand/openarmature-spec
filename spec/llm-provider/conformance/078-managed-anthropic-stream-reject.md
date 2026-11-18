# 078: The Anthropic Body `stream` Field Is Managed in Both Modes

Verifies llm-provider §8.2.1 (proposals 0108 and 0128). The Anthropic body `stream` field is the wire
realization of the declared `stream` argument. The mapping sends `stream: true` for a `stream`-set call and no
`stream` key otherwise. Every call fixes a stream mode, so the field is managed on every call. An extras
`stream` that matches the call's mode is a no-op, and one that conflicts with it is rejected before sending.

**Spec sections exercised:**

- llm-provider §8.2.1: the managed `stream` field and its match and conflict rules.
- llm-provider §6 *Managed-field collision*: a non-additive managed field takes a matching extras value as a
  no-op and rejects a conflicting one pre-send.
- llm-provider §7: `provider_invalid_request` at pre-send validation, with no request sent.

**Cases:**

1. `extras_stream_true_on_unstreamed_call_rejected_pre_send`: extras `stream: true` on a call without
   `stream` is rejected, and no request is sent.
2. `extras_stream_false_on_streamed_call_rejected_pre_send`: extras `stream: false` on a `stream`-set call is
   rejected, with no token events and no request sent.
3. `extras_stream_true_on_streamed_call_no_op`: extras `stream: true` on a `stream`-set call is a no-op. The
   wire body is exact, so it carries `stream: true` once, and the streamed `Response` assembles.
4. `extras_stream_false_on_unstreamed_call_no_op`: extras `stream: false` on a call without `stream` is a
   no-op, and the wire body carries no `stream` key.

**What passes:**

- The two pre-send rejections, and the two no-op calls with the wire bodies and `Response`s above.

**What fails:**

- Forwarding a conflicting extras `stream` to the wire, so the response comes back in the mode the call did
  not fix.
- Letting the extras value switch the call's mode, or dropping it silently and sending the request.
- Forwarding a matching `stream: false`, which puts a `stream` key on the atomic request.
- Rejecting a matching extras value.
