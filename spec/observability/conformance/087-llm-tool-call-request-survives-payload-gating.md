# 087 — LLM tool-call request: payload gating

Verifies observability §5.5.1 / §5.5.10 (proposal 0076): the ungated identity
projections render regardless of `disable_provider_payload`, while the gated full
serialization `openarmature.llm.output.tool_calls` (which carries the arguments)
is suppressed when the flag is on. So "which tools were requested" survives the
default payload-off posture; the arguments do not.

## Spec coverage

- §5.5.10 — `count` / `names` / `ids` are ungated identity (not gated by
  `disable_provider_payload`, §5.5.4).
- §5.5.1 — `openarmature.llm.output.tool_calls` (the full `[{id, name,
  arguments}]` serialization) is a payload attribute, gated by
  `disable_provider_payload`.

## Cases

1. `identity_survives_payload_disabled` — `disable_provider_payload=True`
   (default): the identity projections (`count` / `names` / `ids`) still emit;
   the gated `openarmature.llm.output.tool_calls` (carrying the arguments) is
   suppressed.
2. `full_serialization_present_when_payload_enabled` —
   `disable_provider_payload=False`: the same identity projections emit
   identically (flag-independent), and the gated `output.tool_calls` is
   additionally present (parsing to the `[{id, name, arguments}]` structure per
   §5.5.5).

## Anti-cases (would indicate a broken implementation)

- The identity projections suppressed when `disable_provider_payload=True` —
  treating identifiers as payload defeats the point (tool-request visibility
  under the default privacy posture).
- The gated `openarmature.llm.output.tool_calls` (arguments) emitted when
  `disable_provider_payload=True` — leaking payload under the privacy default.
