# 087 — LLM tool-call request attributes survive payload gating

Verifies observability §5.5.10 (proposal 0076): the tool-call request attributes
are identity, not payload — `disable_provider_payload` does NOT gate them, so they
render in the default payload-off posture while the tool *arguments* stay in the
gated `openarmature.llm.output.content`.

## Spec coverage

- §5.5.10 — `count` / `names` / `ids` are ungated by `disable_provider_payload`
  (§5.5.4); the arguments remain in `output.content` (§5.5.1), gated.

## Cases

1. `tool_call_attrs_present_with_payload_disabled` — `disable_provider_payload=True`
   (default): `count` / `names` / `ids` still emit; `output.content` (the
   serialized arguments) is suppressed.
2. `tool_call_attrs_present_with_payload_enabled` — `disable_provider_payload=False`:
   the same `count` / `names` / `ids` emit identically (flag-independent); the
   output payload is additionally populated.

## Anti-cases (would indicate a broken implementation)

- `count` / `names` / `ids` suppressed when `disable_provider_payload=True` —
  treating identifiers as payload defeats the point (tool-request visibility under
  the default privacy posture).
- The tool arguments leaking into the `tool_calls.*` attributes (they belong only
  in the gated `output.content`).
