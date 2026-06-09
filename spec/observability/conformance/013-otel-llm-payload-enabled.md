# 013 — LLM Payload Enabled

Verifies §5.5.1 input/output payload attributes emit when `disable_provider_payload = False` on the
observer. The `openarmature.llm.input.messages` attribute carries a JSON-encoded message list
that parses to the §3 message structure originally sent to the provider; the
`openarmature.llm.output.content` attribute carries the assistant content verbatim.

**Spec sections exercised:**

- §5.5.1 `openarmature.llm.input.messages` — JSON-encoded message list per llm-provider §3.
- §5.5.1 `openarmature.llm.output.content` — assistant content verbatim from §6
  `message.content`.
- §5.5.1 `openarmature.llm.request.extras` — absent when no `RuntimeConfig` extras supplied.
- §5.5.6 cross-impl consistency — within-implementation determinism; parses to equivalent
  message structure (not bytewise equality).

**Cases:**

1. `payload_enabled` — two-turn conversation (system + user). `disable_provider_payload = False`.
   Mock provider returns assistant content "hello back".

**Harness extensions:**

- `attribute_parses_as_messages` — mapping of attribute name → expected §3 message list. The
  harness parses the attribute string as JSON and asserts the result is structurally equivalent
  to the supplied list (per llm-provider §3 message shape: role, content, optional tool_calls,
  optional tool_call_id). Bytewise comparison of the JSON is NOT required.
- `attributes_absent` (per fixture 012).

**What passes:**

- `openarmature.llm.input.messages` is a string that parses as a JSON array of message records
  matching the supplied list.
- `openarmature.llm.output.content` equals `"hello back"`.
- `openarmature.llm.request.extras` is not present on the span.

**What fails:**

- The input.messages attribute is missing → payload gating logic ignores `disable_provider_payload`.
- The parsed JSON differs structurally from the expected message list (e.g., a message is
  dropped, role is wrong, content is reformatted).
- `openarmature.llm.output.content` is re-serialized rather than verbatim (would surface if the
  implementation accidentally JSON-encoded a string-shaped content).
- `openarmature.llm.request.extras` is emitted even though no extras were supplied.
