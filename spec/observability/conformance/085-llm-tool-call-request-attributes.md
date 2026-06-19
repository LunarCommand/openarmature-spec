# 085 — LLM tool-call request attributes (identity projections)

Verifies observability §5.5.10 (proposal 0076): a completion whose assistant
message requests tool calls surfaces the ungated identity projections on the
`openarmature.llm.complete` span.

## Spec coverage

- §5.5.10 — `openarmature.llm.output.tool_calls.count` / `.names` / `.ids`
  populated from the assistant message's `tool_calls` (llm-provider §3).
- §5.5.10 — `.names` and `.ids` are equal-length, index-aligned, in request
  order; `.count` equals their length.

## Cases

1. `two_requested_tool_calls_emit_count_names_ids` — the model requests
   `get_weather` then `get_time`; the span carries `count = 2`,
   `names = ["get_weather", "get_time"]`, `ids = ["call_a", "call_b"]`, with
   `names[i]` / `ids[i]` describing the same call in emission order. (Default
   payload-off posture, so the gated `openarmature.llm.output.tool_calls` full
   serialization is absent — see fixture 087 for the gated layer.)

## Anti-cases (would indicate a broken implementation)

- Only `count` (or only the arrays) emitted — the family is incomplete.
- `names` / `ids` out of request order, or not index-aligned with each other.
- The identity projections suppressed under the default payload-off posture
  (they are ungated identity, not payload — see fixture 087).
