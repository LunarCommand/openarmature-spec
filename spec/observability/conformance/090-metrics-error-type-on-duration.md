# 090 — Metrics: error.type on an errored call's duration

Verifies observability §11.2 / §11.3 (proposal 0067): an errored provider call
still records a duration observation, carrying the `error.type` dimension, and
records no token-usage observation.

## Spec coverage

- §11.2 — the duration histogram records **including** attempts that ended in error.
- §11.3 — `gen_ai.request.model` and `gen_ai.system` remain required on the duration
  metric even on a failure; `error.type` (the llm-provider §7 category, from the typed
  `LlmFailedEvent` per proposal 0058) is added — duration-only, present only on failure.
- §11.2 — no token-usage observation when the call returned no usage (failure).

## Cases

1. `errored_call_records_duration_with_error_type` — a 503 →
   `provider_unavailable` failure records one duration observation with
   `error.type="provider_unavailable"` and zero token-usage observations; the
   exception still propagates (`expected_error`).

## Anti-cases

- No duration observation on failure (a failed attempt is still a latency sample).
- A token-usage observation recorded for a call that returned no usage.
- `error.type` on the token-usage instrument (it is a duration-only dimension).
