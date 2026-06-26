# 125 — Metrics: token usage recorded on a structured-output failure

Verifies observability §11.2's reconciled token-usage rule (per proposal 0082): a
`structured_output_invalid` failure carries a usage record (the graph-engine §6 `LlmFailedEvent.usage`
surface), so — alone among failure categories — it records a `openarmature.gen_ai.client.token.usage`
observation like a completion, with the §11.3 dimensions. The `operation.duration` instrument
additionally records its `error.type` dimension. Runs the fixture-120 truncation case with
`enable_metrics` on.

**Spec coverage:**

- §11.2 — the token-usage histogram records for an attempt that carries a usage record; a
  `structured_output_invalid` failure now carries one (proposal 0082), so it records like a
  completion. Other failure categories (no usage record) still contribute nothing — the contrast to
  fixture 090.
- §11.3 — dimensions `openarmature.gen_ai.operation` (`"chat"`), `gen_ai.request.model`,
  `gen_ai.system`, `openarmature.gen_ai.token.type` (`"input"` / `"output"`); `error.type` on the
  duration instrument carrying the §7 category.
- §11.4 — token values asserted (fixed-usage mock); duration value not.
- §11.5 / conformance-adapter §6.9 — the metric-capture primitive + the `metrics:` assertion shape
  (per fixtures 088–091).

**Cases:**

1. `structured_output_failure_records_token_usage_and_duration_with_error_type` — Truncation failure
   (`finish_reason: "length"`, usage {input 20, output 16}) with `enable_metrics = True`. Two
   token-usage observations (20 / `"input"`, 16 / `"output"`) are recorded for the failed call, and
   one duration observation carrying `error.type = "structured_output_invalid"`. The exception still
   propagates.

**Anti-cases:**

- No token-usage observation recorded for the failed call — the pre-0082 behavior, which dropped a
  `structured_output_invalid` failure (a real token spend) out of cost accounting.
- A single token-usage observation (input + output collapsed) — the contract is two.
- The duration value asserted (nondeterministic, §11.4).
- `error.type` placed on the token-usage instrument (it is a duration-only dimension, §11.3).
- A token-usage observation recorded for a *non*-`structured_output_invalid` failure (those carry no
  usage record — fixture 090's `provider_unavailable` records duration + `error.type` only).
