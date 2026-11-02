# 062 — `LlmCompletionEvent.request_params` populated with supplied subset

Verifies graph-engine §6's `LlmCompletionEvent.request_params` field (per proposal 0057). The
mapping carries the §5.5.2 GenAI request-parameter family with **absence-is-meaningful**
semantics — only parameters the caller actually supplied appear in the mapping.

**Spec sections exercised:**

- graph-engine §6 — `LlmCompletionEvent.request_params` field (proposal 0057).
- observability §5.5.2 — GenAI request-parameter family + absence rule
  ("MUST NOT emit the attribute" when not set).

**Cases:**

1. `request_params_populated_with_supplied_subset` — Call passes `temperature=0.7` and
   `max_tokens=512`; no other §5.5.2 parameters supplied. The typed event's `request_params`
   carries exactly those two keys; the other five §5.5.2 parameters
   (`top_p`, `seed`, `frequency_penalty`, `presence_penalty`, `stop_sequences`) MUST NOT
   appear in the mapping.

**How absence is asserted:** an event's `request_params` is compared exactly
(conformance-adapter §8.4). The written mapping is the whole value, so a key it leaves out
must be absent from the event's `request_params`.

**What passes:**

- `request_params` is a mapping carrying exactly `{temperature: 0.7, max_tokens: 512}`.
- None of the other §5.5.2 parameter keys (`top_p`, `seed`, `frequency_penalty`,
  `presence_penalty`, `stop_sequences`) appear in the mapping.

**What fails:**

- `request_params` carries one of the other §5.5.2 keys with a default value
  (e.g., `top_p: 1.0`) — violates the absence-is-meaningful rule.
- `request_params` is a flat-field record rather than a mapping (proposal 0057 §5 mandates
  mapping shape).
- Keys use the full `gen_ai.request.*` prefix (e.g., `gen_ai.request.temperature`); proposal
  0057's spec text mandates keys without the prefix (e.g., `temperature`).
