# 086 — LLM tool-call request attributes (absent)

Verifies observability §5.5.1 / §5.5.10 (proposal 0076): a completion that
requests no tools emits neither the gated `openarmature.llm.output.tool_calls`
serialization nor the ungated identity projections — absence cleanly means "no
tools requested," distinct from `count = 0`.

## Spec coverage

- §5.5.1 / §5.5.10 — the tool-call attribute family is emitted only on a
  tool-calling completion (count ≥ 1); absent otherwise.

## Cases

1. `no_requested_tool_calls_omits_attributes` — a plain completion (assistant
   content, no `tool_calls`) emits none of `output.tool_calls`, `.count`,
   `.names`, or `.ids`.

## Anti-cases (would indicate a broken implementation)

- `count = 0` (and/or empty `names` / `ids` arrays, or an empty
  `output.tool_calls`) emitted on a non-tool completion — adds noise to every
  span and conflates "no tools" with "zero."
- The attributes emitted with stale / leftover values from a prior call.
