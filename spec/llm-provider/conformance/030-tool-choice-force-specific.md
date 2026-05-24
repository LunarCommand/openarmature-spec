# 030 — Tool Choice Force Specific

Verifies the `{type: "tool", name: X}` force-specific mode of §5
`tool_choice` and its §8.1.1 OpenAI wire mapping (with the spec
`type: "tool"` → wire `type: "function"` rename).

**Spec sections exercised:**

- §5 `complete()` — `tool_choice = {type: "tool", name: X}` force-
  specific mode.
- §8.1.1 OpenAI request mapping — force-specific row:
  `{type: "tool", name: X}` → `tool_choice: {type: "function", function: {name: X}}`.
  The rename from spec `tool` to wire `function` is performed by the
  implementation when constructing the wire body.
- §6 Response shape — the returned tool call's `name` matches the
  forced tool when the mock returns a constraint-compliant response.

**What passes:**

- Outbound wire `tool_choice.type == "function"` (NOT `"tool"` — the
  spec→wire rename is mandatory).
- Outbound wire `tool_choice.function.name == "search"`.
- Returned tool call's `name == "search"`.
- The `summarize` tool in the supplied `tools` list is forwarded on
  the wire (the force-specific constraint doesn't filter tools; the
  full list goes to the model with one tool forced).

**What fails:**

- Wire `tool_choice` has `type: "tool"` (forgot the rename).
- Wire `tool_choice.function.name` is missing or wrong.
- The implementation strips `summarize` from `tools` on the wire
  because it's not the forced tool — incorrect; the full list still
  goes.

**Notes:**

- Two tools (`search` + `summarize`) are supplied to exercise the
  list-isn't-filtered invariant. A future fixture could exercise the
  validation case where `name` doesn't appear in the tools list —
  that's fixture 031's responsibility.
- The mock returns a constraint-compliant response (calls `search`).
  Same framework-doesn't-enforce-post-hoc principle from fixture 029
  applies; this fixture verifies wire mapping + response surfacing,
  not enforcement.
