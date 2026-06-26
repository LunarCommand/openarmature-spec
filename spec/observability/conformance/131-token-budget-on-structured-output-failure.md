# 131 — Token budget on a structured-output failure (and the no-usage contrast)

Verifies observability §5.5.15 / §11.2 (per proposal 0083) on the failure path: the token-budget signal
evaluates on a `structured_output_invalid` `LlmFailedEvent` — the one failure category that carries
`usage` (proposal 0082) — with full parity to the completion path, and does **not** evaluate on a
failure that carries no usage. The budget reaches the failed call via the `renders_prompt:`
prompt-context binding, surfacing on the graph-engine §6 `LlmFailedEvent.token_budget` field.

**Spec sections exercised:**

- graph-engine §6 — `LlmFailedEvent.token_budget` field; budget *evaluation* occurs on this variant only
  for `structured_output_invalid` (the category carrying `usage`, proposal 0082); other categories may
  populate the field but no evaluation occurs (proposal 0083).
- observability §5.5.15 — the reactive signal is evaluated from the actual usage on the terminal typed
  event; a `structured_output_invalid` `LlmFailedEvent` is in scope, other failure categories are not
  (no usage to compare against).
- observability §11.2 — the exceeded Counter + `.utilization` Histogram fire on the failure event when a
  budget was exceeded, "keeping coverage aligned with the `token.usage` instrument" (which also records
  on the `structured_output_invalid` failure, fixture 125).
- observability §5.5.7 / proposal 0082 — the `structured_output_invalid` response-side surface
  (`usage`, `finish_reason`) the budget evaluation reads; `usage` null for `provider_unavailable`
  (fixture 122).

**Cases:**

1. `structured_output_failure_evaluates_token_budget_on_failure_event` — Budgeted prompt
   (`input_max_tokens: 10`) + `response_schema`; the mock returns truncated JSON (`finish_reason:
   "length"`) with usage `{prompt 20, completion 16, total 36}`, so `complete()` raises
   `structured_output_invalid`. `enable_metrics = True`. The `LlmFailedEvent.token_budget` is populated
   `{input_max_tokens: 10, total_max_tokens: null}`; `prompt_tokens` 20 > 10, so the ERROR span carries
   `openarmature.llm.token_budget.exceeded = true`, the exceeded counter records once (`kind =
   "input"`), and a utilization observation is recorded at `20 / 10 = 2.0` (`kind = "input"`) — all on
   the failure event. The exception propagates.
2. `provider_unavailable_failure_populates_budget_but_no_evaluation` — The same budgeted prompt, but the
   mock returns a 503 → `provider_unavailable`, which carries **no** usage (fixture 122). The
   `LlmFailedEvent.token_budget` is populated (the active prompt's budget) but `usage` is null, so **no**
   evaluation occurs: `openarmature.llm.token_budget.exceeded` is absent (not `false`), and neither
   token-budget instrument records. The exception propagates.

**Harness extensions:** combines `renders_prompt:` + the prompt's `token_budget` config with
`calls_llm.response_schema` (the structured-output mock, fixtures 120 / 022 / 023), `enable_metrics:`,
the `metrics:` assertion shape, and the `expected_error:` + `exception_propagates_alongside_typed_event`
dispatch pattern (fixtures 069 / 120).

**Harness note (absence assertion, case 2):** as in fixtures 128 / 129, "neither token-budget instrument
recorded" is expressed as the fixture-specific invariant
`no_token_budget_instrument_observations_without_usage` (§5.9) — the `metrics:` directive asserts
recorded observations and cannot express per-instrument absence short of `metrics: []`. Case 2 declares
no `metrics:` block (no token-budget observations are expected and metrics are otherwise out of this
case's scope); the invariant carries the absence assertion.

**What passes:**

- Case 1: `LlmFailedEvent.token_budget == {input_max_tokens: 10, total_max_tokens: null}` with
  `error_category = "structured_output_invalid"`; `openarmature.llm.token_budget.exceeded = true` on the
  ERROR span; the exceeded counter (`kind = "input"`) and a `2.0` utilization observation
  (`kind = "input"`) recorded; exception propagates.
- Case 2: `LlmFailedEvent.token_budget` populated with `usage == null` and
  `error_category = "provider_unavailable"`; no `openarmature.llm.token_budget.exceeded` attribute;
  neither token-budget instrument records; exception propagates.

**What fails:**

- The budget evaluation is skipped on the `structured_output_invalid` failure (the impl evaluates only
  on completions), so the exceeded signal / counter / utilization are absent despite a real over-budget
  spend — the failure-path-parity defect proposal 0083 closes alongside 0082's usage surface.
- Case 2 evaluates the budget against a null / zero usage (a divide-by-absent or false-positive
  exceedance) — `provider_unavailable` carries no usage and must not be evaluated.
- Case 2 emits `openarmature.llm.token_budget.exceeded = false` (the signal requires usage; with none,
  it is absent, not `false`).
- The utilization value is asserted with a comparison matcher rather than the exact `2.0` (§5.8 /
  §11.4).
