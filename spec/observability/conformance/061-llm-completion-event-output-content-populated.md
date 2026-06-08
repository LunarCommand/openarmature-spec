# 061 — `LlmCompletionEvent.output_content` populated / null companion

Verifies graph-engine §6's `LlmCompletionEvent.output_content` field (per proposal 0057).
Populated verbatim per llm-provider §6 `Response.message.content` for text responses; null on
tool-call-only assistant messages per the structured-response / tool-call mutual-exclusion
rule.

**Spec sections exercised:**

- graph-engine §6 — `LlmCompletionEvent.output_content` field (proposal 0057).
- llm-provider §6 — `Response.message.content` shape + tool-call mutual-exclusion.
- observability §5.5.1 — the equivalent `openarmature.llm.output.content` framing.

**Cases:**

1. `output_content_populated_for_text_response` — Assistant returns `content="Done."` with
   `finish_reason=stop`. The typed event's `output_content` carries the content verbatim.
2. `output_content_null_for_tool_call_only_response` — Assistant returns `tool_calls` (no
   content) with `finish_reason=tool_calls`. The typed event's `output_content` is null per
   the structured-response / tool-call mutual-exclusion rule.

**What passes:**

- Case 1: `output_content == "Done."` exactly.
- Case 2: `output_content == null`; `finish_reason == "tool_calls"`.

**What fails:**

- Case 1: `output_content` truncated, transformed, or null.
- Case 2: `output_content` is non-null when the assistant message carried `tool_calls` with
  empty content (the spec mandates null on the structured-response / tool-call mutual-
  exclusion case).
- Case 2: `output_content` is a stringified representation of the tool calls (the spec carves
  tool_calls separately on the assistant message; `output_content` is content-only).
