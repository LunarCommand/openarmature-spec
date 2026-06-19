# 088 — LLM metrics: token usage + operation duration

Verifies observability §11.2 / §11.3 (proposal 0067): an LLM completion with
`enable_metrics` on records the token-usage and operation-duration histograms.

## Spec coverage

- §11.2 — `openarmature.gen_ai.client.token.usage` records **two** observations per
  LLM completion (input + output), `openarmature.gen_ai.client.operation.duration`
  records one.
- §11.3 — dimensions `openarmature.gen_ai.operation` (`"chat"`),
  `gen_ai.request.model`, `openarmature.gen_ai.token.type` (`"input"` / `"output"`).
- §11.4 — token values are asserted (fixed-usage mock); the duration value is not.
- conformance-adapter §6.9 / §5.8 — the metric-capture primitive + the `metrics:`
  assertion.

## Cases

1. `llm_completion_records_token_and_duration` — usage {input 5, output 1} → two
   token-usage observations (5 / `"input"`, 1 / `"output"`) and one duration
   observation (dimensions only).

## Anti-cases

- A single token-usage observation (input + output collapsed) — the contract is two.
- The duration value asserted (it is nondeterministic, §11.4).
- Metrics recorded but missing the operation / model / token-type dimensions.
