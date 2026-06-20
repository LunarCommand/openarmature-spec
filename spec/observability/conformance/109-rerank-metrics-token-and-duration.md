# 109 — Rerank metrics (token + duration, operation `rerank`)

Verifies observability §11: a rerank call joins the operation-generic GenAI metric instruments,
dimensioned by `openarmature.gen_ai.operation = "rerank"`. The token-usage histogram records a rerank
call's `input_tokens` as `"input"` **only when reported** (rerank has no output tokens; `search_units`
is a billing unit, not a token); the duration histogram records every rerank call, carrying
`error.type` on failure (sourced from `RerankFailedEvent`).

**Spec sections exercised:**

- observability §11.2 / §11.3 — operation-generic instruments; the `rerank` operation dimension;
  conditional rerank token-usage; `error.type` sourced from `RerankFailedEvent`.

**Cases:**

1. `rerank_records_input_token_and_duration` — provider reports `input_tokens=5`; records token.usage
   `input=5` + duration, both `operation="rerank"`.
2. `rerank_search_units_only_records_no_token_usage` — provider reports `search_units` only; **no**
   token.usage observation, duration still recorded.
3. `errored_rerank_records_duration_with_error_type` — 503 → `provider_unavailable`; duration carries
   `error.type="provider_unavailable"`, no token.usage.

**What passes:**

- Rerank metrics carry `operation="rerank"`; token.usage fires only on reported `input_tokens`;
  duration always recorded (with `error.type` on failure).

**What fails:**

- token.usage recorded for a search-units-only rerank call (treating `search_units` as a token).
- Missing `error.type` on an errored rerank duration observation, or a wrong operation dimension.
