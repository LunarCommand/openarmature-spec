# 018 — LLM Request Extras

Verifies §5.5.1: `openarmature.llm.request.extras` is emitted as a JSON-encoded object carrying
the `RuntimeConfig` extras mapping (per llm-provider §6 `extra="allow"`) when the extras mapping
is non-empty and `disable_llm_payload = False`.

**Spec sections exercised:**

- §5.5.1 `openarmature.llm.request.extras` — JSON-encoded object, OA-shape, default-off via
  `disable_llm_payload`.

**Cases:**

1. `extras_emitted` — `RuntimeConfig` carries `temperature: 0.7` and an extras bag with
   `frequency_penalty: 0.5`. `disable_llm_payload = False`. The span carries
   `gen_ai.request.temperature` (per §5.5.2) and `openarmature.llm.request.extras` (per §5.5.1)
   as a JSON-encoded object.

**Harness extensions:**

- `extras` block under `config` — provider-specific pass-through fields routed through
  `RuntimeConfig`'s `extra="allow"` bag.
- `attribute_parses_as_object` — mapping of attribute name → expected JSON-decoded object. The
  harness parses the attribute string as JSON and asserts structural equivalence to the supplied
  object. Bytewise JSON comparison is NOT required.

**What passes:**

- `gen_ai.request.temperature: 0.7` is present on the span.
- `openarmature.llm.request.extras` parses to an object equivalent to `{frequency_penalty: 0.5}`.

**What fails:**

- Extras attribute is absent — implementation gated `request.extras` under
  `disable_llm_payload = True` semantics (incorrect — the spec says default-off only when the
  user has NOT opted in; the user IS opted in here).
- Extras content is duplicated in `gen_ai.request.*` namespace — implementation tried to map
  provider-specific extras into the GenAI semconv (incorrect — extras stay OA-shape).
- `frequency_penalty` is emitted as `gen_ai.request.frequency_penalty` — implementation
  generalized too aggressively (not a settled semconv name; stays in extras).
