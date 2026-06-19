# 085 — LLM tool-call request attributes (populated)

Verifies observability §5.5.10 (proposal 0076): a completion whose assistant
message requests tool calls surfaces them as first-class, queryable attributes on
the `openarmature.llm.complete` span.

## Spec coverage

- §5.5.10 — `openarmature.llm.tool_calls.count` / `.names` / `.ids` populated from
  the assistant message's `tool_calls` (llm-provider §3).
- §5.5.10 — `.names` and `.ids` are equal-length, index-aligned, in request order;
  `.count` equals their length.

## Cases

1. `two_requested_tool_calls_emit_count_names_ids` — the model requests
   `get_weather` then `get_time`; the span carries `count = 2`,
   `names = ["get_weather", "get_time"]`, `ids = ["call_a", "call_b"]`, with
   `names[i]` / `ids[i]` describing the same call in emission order.

## Anti-cases (would indicate a broken implementation)

- Only `count` (or only the arrays) emitted — the family is incomplete.
- `names` / `ids` out of request order, or not index-aligned with each other.
- The tool calls left only in the JSON output payload (`output.content`), not
  promoted to the first-class `tool_calls.*` attributes.
