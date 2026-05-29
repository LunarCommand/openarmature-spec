# 047 — Gemini tool-choice modes

Verifies §8.3.1 `tool_choice` → `toolConfig.functionCallingConfig` mapping across all modes.

**Spec sections exercised:**

- §8.3.1 tool-choice mapping — `None`/absent → field omitted; `"auto"` → `AUTO`; `"required"` →
  `ANY`; `"none"` → `NONE`; `{type: "tool", name: X}` → `ANY` + `allowedFunctionNames: [X]`.

**What passes:**

- Absent `tool_choice` emits no `toolConfig` at all.
- `"required"` renames to Gemini's `ANY` (the load-bearing cross-vendor rename).
- A specific-tool choice emits `ANY` mode with `allowedFunctionNames` constrained to that name.

**What fails:**

- `"required"` emitted as `REQUIRED` (a non-existent Gemini mode) instead of `ANY`.
- A `toolConfig` block emitted when `tool_choice` is absent.
- A specific-tool choice emitted without `allowedFunctionNames` (an unconstrained `ANY`).
