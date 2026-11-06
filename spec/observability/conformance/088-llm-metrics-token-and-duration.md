# 088 — LLM metrics: token usage + operation duration

Verifies observability §11.2 / §11.3 (proposal 0067): an LLM completion with
`enable_metrics` on records the token-usage and operation-duration histograms.

## Spec coverage

- §11.2 — `openarmature.gen_ai.client.token.usage` records **two** observations per
  LLM completion (input + output), `openarmature.gen_ai.client.operation.duration`
  records one per attempt (one in case 1).
- §11.3 — dimensions `openarmature.gen_ai.operation` (`"chat"`),
  `gen_ai.request.model`, `gen_ai.system`, `openarmature.gen_ai.token.type`
  (`"input"` / `"output"`).
- §11.4 — token values are asserted (fixed-usage mock); the duration value is not.
- §11.2 *Call-level retry*: the duration histogram records once per attempt, a failed attempt
  carrying `error.type`, and token usage records only for the attempt that returned a usage record.
- §11.5: the capture records each measurement individually, so two identical recordings appear
  twice in the complete `metrics` list.
- conformance-adapter §6.9 / §5.8 — the metric-capture primitive + the `metrics:`
  assertion.

## Cases

1. `llm_completion_records_token_and_duration` — usage {input 5, output 1} → two
   token-usage observations (5 / `"input"`, 1 / `"output"`) and one duration
   observation (dimensions only).
2. `retried_call_records_each_attempt`: two 503 attempts, then a success with the same usage →
   two identical duration observations carrying `error.type: provider_unavailable`, one duration
   observation without it, and the same two token-usage observations.

## Anti-cases

- A single token-usage observation (input + output collapsed) — the contract is two.
- The duration value asserted (it is nondeterministic, §11.4).
- Metrics recorded but missing the operation / model / token-type dimensions.
- Case 2: the two identical failed-attempt recordings merged into one, a duration recorded once
  per call rather than once per attempt, or token usage recorded for a failed attempt.
