# 029 — Tool Choice Modes

Foundational fixture for the §5 `tool_choice` parameter and its §8.1.1
OpenAI wire mapping. Four cases covering the three string modes plus
the default (no `tool_choice` supplied). For each case, verifies the
outbound wire shape and end-to-end response mapping.

**Spec sections exercised:**

- §5 `complete()` — `tool_choice` parameter (auto / required / none /
  default).
- §8.1.1 OpenAI request mapping — `tool_choice` wire row:
  - None / absent → field omitted from wire body
  - `"auto"` → `tool_choice: "auto"`
  - `"required"` → `tool_choice: "required"`
  - `"none"` → `tool_choice: "none"`
- §6 Response shape — `finish_reason` surfaces what the provider
  returned; the framework does NOT enforce `tool_choice` post-hoc.

**What passes:**

- `tool_choice_default_omits_wire_field` — no `tool_choice` supplied;
  wire body has NO `tool_choice` key
  (`expected_wire_request_checks.tool_choice_absent: true`).
  v0.4.0 backward compatibility verified.
- `tool_choice_auto_emits_wire_field` — explicit auto; wire body has
  `tool_choice: "auto"`.
- `tool_choice_required_emits_wire_field_mock_returns_tool_call` —
  required; wire body has `tool_choice: "required"`; mock returns
  tool_calls; `Response.finish_reason == "tool_calls"`.
- `tool_choice_none_emits_wire_field_mock_returns_content` — none;
  wire body has `tool_choice: "none"`; mock returns content-only;
  `Response.finish_reason == "stop"`.

**What fails:**

- Default case puts `tool_choice` on the wire (any value) — would
  break v0.4.0 backward compat.
- Default case omits the `tool_choice` field BUT the implementation
  defaults it to `auto` internally before sending — also a backward
  compat regression (callers who never opted in shouldn't see new
  wire shape).
- `auto` / `required` / `none` cases omit the field from the wire —
  would mean the implementation isn't propagating the parameter.
- The required / none cases assert framework enforcement instead of
  response surfacing (e.g., raise on a noncompliant mock response).
  §5 is explicit that the framework does NOT re-validate.

**Notes:**

- New harness primitive: `expected_wire_request_checks.tool_choice_absent: true`
  — sibling-to-`expected_wire_request` block; asserts that the named
  key is NOT present in the wire body (vs present-with-a-specific-value,
  which the existing `expected_wire_request` matchers cover). Distinct
  from `tool_choice: null` (asserting the key IS present with a null
  value). Follows fixture 027's `expected_wire_request_checks.response_format_absent`
  precedent so `expected_wire_request` stays strictly wire-shaped.
- The mock provider configurations for the required / none cases are
  deliberately constraint-compliant: required → mock returns
  tool_calls, none → mock returns content. The fixture's job is wire
  mapping + response mapping verification, not enforcement testing.
  An enforcement-mode fixture (mock returns non-compliant response,
  framework still surfaces it) would be a separate concern that the
  spec deliberately does NOT require — provider compliance is
  observable from the returned fields but is not framework-policed.
- The force-specific mode (`{type: "tool", name: X}`) is exercised by
  the dedicated fixture 030.
- Validation-failure cases (required-with-empty-tools, force-with-
  empty-tools, force-tool-not-in-list) are exercised by fixture 031.
