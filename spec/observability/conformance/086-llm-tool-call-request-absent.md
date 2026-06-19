# 086 — LLM tool-call request attributes (absent)

Verifies observability §5.5.10 (proposal 0076): a completion that requests no
tools emits none of the `openarmature.llm.tool_calls.*` attributes — absence
cleanly means "no tools requested," distinct from `count = 0`.

## Spec coverage

- §5.5.10 — the attribute family is emitted only on a tool-calling completion
  (count ≥ 1); absent otherwise.

## Cases

1. `no_requested_tool_calls_omits_attributes` — a plain completion (assistant
   content, no `tool_calls`) emits none of `count` / `names` / `ids`.

## Anti-cases (would indicate a broken implementation)

- `count = 0` (and/or empty `names` / `ids` arrays) emitted on a non-tool
  completion — adds noise to every span and conflates "no tools" with "zero."
- The attributes emitted with stale / leftover values from a prior call.
