# 097 — OTel tool span attributes

Verifies observability §5.5.11 (proposal 0063): the tool span's name and
OA-namespace attributes, and that the Development `gen_ai.tool.*` surface is not
emitted in v1.

## Spec coverage

- §5.5.11 — span name `openarmature.tool.call`; OA-namespace `openarmature.tool.*`
  attributes (`name`, `call.id`, `call.arguments`, `call.result`).
- §5.5.11 adoption — `gen_ai.tool.*` (assessed peripheral under the §5.5 carve-out)
  and the `execute_tool` span name are NOT emitted in v1 (mirror-then-adopt).

## Cases

1. `otel_tool_span_uses_oa_namespace_not_gen_ai_tool` — the `openarmature.tool.call`
   span carries the `openarmature.tool.*` attributes; the `gen_ai.tool.*` names and
   `gen_ai.operation.name` are absent.

## Anti-cases

- Emitting `gen_ai.tool.*` attributes or the `execute_tool {gen_ai.tool.name}` span
  name in v1 (before the surface is recognized-core / Stable).
- Using `.complete` (the LLM/embedding suffix) for the tool span name.
