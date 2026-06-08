# 068 — `LlmCompletionEvent.response_model` distinct from request model

Verifies graph-engine §6's `LlmCompletionEvent.response_model` field (per proposal 0057).
The field carries the provider-returned model identifier (`gen_ai.response.model` per
observability §5.5.3), distinct from `model` which carries the requested identifier.

**Spec sections exercised:**

- graph-engine §6 — `LlmCompletionEvent.response_model` field (proposal 0057, bundled
  addition completing §5.5.3 coverage on the typed event).
- observability §5.5.3 — `gen_ai.response.model` attribute distinction from
  `gen_ai.request.model`.

**Cases:**

1. `response_model_distinct_when_provider_returns_specific_identifier` — Provider returns
   `"gpt-4o-2024-08-06"` for a request against the alias `"gpt-4o"`. The typed event's
   `model == "gpt-4o"` and `response_model == "gpt-4o-2024-08-06"`.
2. `response_model_null_when_provider_omits_it` — Provider returns a response body without
   a `model` field. The typed event's `response_model == null`; `model` still carries the
   requested identifier.

**What passes:**

- Case 1: `model` and `response_model` are distinct strings; both populated.
- Case 2: `response_model == null`; `model` populated from the request.

**What fails:**

- Case 1: `model` overwritten with the response identifier (the spec keeps `model` as the
  request-side identifier; `response_model` carries the response-side).
- Case 1: `response_model == null` when the provider DID return a model field.
- Case 2: `response_model` fabricated to equal `model` when the response did not carry one.
