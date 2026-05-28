# 036 — Anthropic tool_choice modes

Verifies the §8.2.1 `tool_choice` mapping across all five shapes.

**Spec sections exercised:**

- §8.2.1 tool_choice table: `None`/absent → field omitted; `"auto"` → `{type: auto}`;
  `"required"` → `{type: any}` (the load-bearing rename); `"none"` → `{type: none}`;
  `{type: "tool", name: X}` → `{type: "tool", name: X}`.

**Cases:**

1. `tool_choice_default_omits_wire_field` — no `tool_choice` supplied; the wire body omits the
   field entirely (asserted via `tool_choice_absent`).
2. `tool_choice_auto` — `{type: auto}`.
3. `tool_choice_required_maps_to_any` — spec `"required"` becomes Anthropic `{type: any}`; mock
   returns a `tool_use` response → `finish_reason: "tool_calls"`.
4. `tool_choice_none` — `{type: none}`.
5. `tool_choice_specific_tool` — `{type: "tool", name: get_weather}`.

**What passes:**

- Each mode produces the exact Anthropic `tool_choice` shape (or omission for the default case).
- `"required"` maps to `{type: any}`, NOT `{type: required}` — the spec's cross-vendor name
  translates to Anthropic's wire name.
- Tool definitions appear under `input_schema`.

**What fails:**

- `"required"` emitted as `{type: required}` (OpenAI's name) rather than `{type: any}`.
- The default case emits a `tool_choice` field instead of omitting it.
