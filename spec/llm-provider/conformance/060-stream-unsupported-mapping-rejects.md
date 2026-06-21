# 060 — Streaming-unsupported mapping rejects a `stream`-set call

Verifies the llm-provider §5 *Provider streaming support* rejection contract. A wire mapping that does not implement streaming MUST reject a `stream`-set call at pre-send validation, raising `provider_invalid_request` (§7), with no token events emitted and no silent atomic fallback — the same mold as `tool_choice` pre-send validation. This is the defined (not undefined) behavior for the §8.2 Anthropic and §8.3 Gemini mappings until their streaming follow-ons land. The fixture introduces the synthetic `mapping: streaming_unsupported_stub` directive (documented in its YAML header per conformance-adapter §3.2) so the contract is tested independently of any one vendor's wire details.

**Spec sections exercised:**

- llm-provider §5 *Provider streaming support* — a non-streaming mapping rejects a `stream`-set call at pre-send validation with `provider_invalid_request`; MUST NOT fall back to atomic or fail mid-call.
- llm-provider §7 — `provider_invalid_request` category.

**Cases:**

1. `stream_set_call_rejected_pre_send_no_token_events_no_fallback` — A `complete(stream=True)` call on the streaming-unsupported mapping. Asserts it raises `provider_invalid_request` at pre-send validation (the mock's empty response list fails the test if any request is sent, confirming pre-send catch and the no-fallback rule), with no `LlmTokenEvent` emitted.
2. `atomic_call_on_same_mapping_still_succeeds` — Control: the same mapping handles an atomic call (stream unset) normally, returning the ordinary atomic `Response`. Confirms the rejection is specific to the `stream`-set request shape, not a broken mapping.

**What passes:**

- A `stream`-set call raises `provider_invalid_request` before any request is sent.
- No token events are emitted on the rejected path.
- No silent atomic fallback (the mock is never reached).
- An atomic call on the same mapping still succeeds.

**What fails:**

- The mapping silently falls back to an atomic call (hiding that streaming was unavailable).
- The call fails mid-stream instead of at pre-send validation, or raises a category other than `provider_invalid_request`.
- Token events emitted for the rejected stream.
