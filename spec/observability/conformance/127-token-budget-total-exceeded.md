# 127 — Token budget: total bound exceeded sets kind "total" counter and utilization

Verifies observability §5.5.15 / §11.2 / §11.3 (per proposal 0083) on the total-bound case — the
companion to fixture 126's input bound. An active prompt declares a `token_budget` whose
`total_max_tokens` sits below the call's actual `total_tokens`, so a successful LLM completion is
evaluated as over budget on the total bound. The exceeded counter and utilization histogram carry
`kind = "total"`.

**Spec sections exercised:**

- graph-engine §6 — `LlmCompletionEvent.token_budget` field (proposal 0083).
- observability §5.5.15 — `openarmature.prompt.token_budget.total_max_tokens` span attribute and
  `openarmature.llm.token_budget.exceeded = true` (the total bound: `total_tokens > total_max_tokens`).
- observability §11.2 — the exceeded Counter and `.utilization` Histogram.
- observability §11.3 — `openarmature.gen_ai.token_budget.kind = "total"` dimension.
- observability §11.4 — deterministic utilization ratio asserted as an exact value.

**Cases:**

1. `token_budget_total_exceeded_sets_attr_counter_and_utilization` — Budgeted prompt
   (`total_max_tokens: 25`, no input bound), mock usage `{prompt 40, completion 10, total 50}`,
   `enable_metrics = True`. `total_tokens` 50 > `total_max_tokens` 25, so the total bound is exceeded.
   The `LlmCompletionEvent.token_budget` carries `{input_max_tokens: null, total_max_tokens: 25}`; the
   span carries `openarmature.prompt.token_budget.total_max_tokens = 25` and
   `openarmature.llm.token_budget.exceeded = true`; the exceeded counter records once with
   `kind = "total"`; a utilization observation is recorded at `50 / 25 = 2.0` with `kind = "total"`.

**Harness extensions:** same as fixture 126 — `renders_prompt:` / `prompt_backend:` with the prompt's
`token_budget` config (prompt-management §3), `enable_metrics:`, and the `metrics:` assertion shape.

**What passes:**

- `LlmCompletionEvent.token_budget == {input_max_tokens: null, total_max_tokens: 25}`.
- `openarmature.llm.token_budget.exceeded == true`; `openarmature.prompt.token_budget.total_max_tokens
  == 25`; `openarmature.prompt.token_budget.input_max_tokens` absent.
- The exceeded counter records once, `kind = "total"`; the utilization histogram records `2.0`,
  `kind = "total"`.

**What fails:**

- The over-budget evaluation uses the wrong bound (e.g. evaluates `prompt_tokens` against the total
  budget) or the wrong comparison.
- The exceeded counter / utilization observation carries `kind = "input"` — the total bound was the one
  breached.
- An `input`-kind observation is recorded despite the prompt declaring no input bound.
- The utilization value is asserted with a comparison matcher rather than the exact `2.0`.
