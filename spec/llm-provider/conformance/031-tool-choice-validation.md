# 031 — Tool Choice Validation

Verifies the three pre-send validation failure modes that §5 +
§7 mandate for `tool_choice`. Each case asserts
`provider_invalid_request` is raised BEFORE any HTTP request goes
out — the implementation's pre-send validation catches them.

**Spec sections exercised:**

- §5 `complete()` operation semantics — `tool_choice` validation
  rules (1) and (2):
  - `tool_choice="required"` requires `tools` non-empty.
  - `tool_choice={type: "tool", name: X}` requires `tools` non-empty
    AND X to be a `Tool.name` in the supplied list.
- §7 Error semantics — `provider_invalid_request` enumerates these
  three new validation failure modes inline under its existing
  description.

**What passes:**

- `required_with_empty_tools` — raises `provider_invalid_request`;
  mock provider's empty `responses` array is never consulted (no HTTP
  request sent).
- `force_specific_with_empty_tools` — same; raises
  `provider_invalid_request`; mock never consulted.
- `force_specific_with_name_not_in_tools_list` — raises
  `provider_invalid_request` because `"search"` is not in
  `[summarize]`; mock never consulted.

**What fails:**

- The implementation sends an HTTP request despite the validation
  failure — would mean the validation isn't pre-send, contradicting
  §5's "before sending" requirement. The mock's empty `responses` list
  would surface this as a "no canned response available" error
  rather than the expected `provider_invalid_request`.
- The implementation raises a different category (e.g.,
  `provider_invalid_response`, a language-native `ValueError`) — the
  spec mandates `provider_invalid_request` specifically.
- The implementation accepts the malformed inputs and somehow returns
  a successful `Response` — would mean validation isn't being
  performed at all.

**Notes:**

- The `mock_provider.responses: []` configuration is load-bearing
  here: it asserts negative coverage (no request should reach the
  mock). If the implementation incorrectly sends a request, the
  mock's empty list causes a distinct failure mode that distinguishes
  "validation didn't fire" from "validation fired with the wrong
  category."
- The two `force_specific` cases distinguish empty-tools vs
  name-not-in-list scenarios. Both route to the same
  `provider_invalid_request` category but exercise different code
  paths in a well-structured implementation. Implementations that
  short-circuit on `tools` empty without checking the name-in-list
  path still pass — the spec requires the category, not the internal
  code structure.
- This fixture explicitly does NOT exercise `tool_choice="auto"` or
  `tool_choice="none"` with empty tools — both are spec-valid (per §5
  operation semantics rule (3): "auto and none have no tools-related
  preconditions"). A future regression fixture could verify those
  cases don't raise; covered as part of fixture 029's default-case
  reasoning.
