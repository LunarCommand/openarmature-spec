# 063 — `LlmCompletionEvent.request_extras` populated as native mapping

Verifies graph-engine §6's `LlmCompletionEvent.request_extras` field (per proposal 0057). The
field carries the `RuntimeConfig` extras pass-through bag (per llm-provider §6) in
typed-event-native mapping form — NOT the JSON-encoded string form observability §5.5.1
emits on the OTel span.

**Spec sections exercised:**

- graph-engine §6 — `LlmCompletionEvent.request_extras` field (proposal 0057).
- llm-provider §6 — `RuntimeConfig` extras pass-through contract.
- observability §5.5.1 — the equivalent `openarmature.llm.request.extras` JSON-encoded
  attribute (distinct serialization form).

**Cases:**

1. `request_extras_populated_as_native_mapping` — Call passes RuntimeConfig with one extras
   field (`repetition_penalty`, a provider-specific sampling parameter). The typed event's
   `request_extras` carries the mapping natively.

**What passes:**

- `request_extras` is a native mapping carrying `{repetition_penalty: 1.05}`.

**What fails:**

- `request_extras` is a JSON-encoded string (the §5.5.1 span attribute form is JSON-encoded;
  the typed event field is native).
- `request_extras` is null when extras were supplied.
- The extras mapping is transformed (renamed, namespaced) — the pass-through contract per
  llm-provider §6 mandates extras flow through untouched.
