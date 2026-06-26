# 126 — Token budget: input bound exceeded sets attr, counter, and utilization

Verifies observability §5.5.15's reactive over-budget signal and §11.2 token-budget instruments (per
proposal 0083) on the input-bound case: an active prompt declares a `token_budget` whose
`input_max_tokens` sits below the call's actual `prompt_tokens`, so a successful LLM completion is
evaluated as over budget. The budget reaches the call via the `renders_prompt:` prompt-context binding
(the same mechanism that populates `active_prompt`, fixture 064), surfacing on the graph-engine §6
`LlmCompletionEvent.token_budget` field.

**Spec sections exercised:**

- graph-engine §6 — `LlmCompletionEvent.token_budget` field (`{input_max_tokens, total_max_tokens}`,
  sourced from `Prompt.token_budget` via the prompt-context binding, proposal 0083).
- observability §5.5.15 — `openarmature.prompt.token_budget.input_max_tokens` span attribute (the
  declared bound) and `openarmature.llm.token_budget.exceeded = true` (the reactive over-budget signal,
  `prompt_tokens > input_max_tokens`).
- observability §11.2 — the `openarmature.gen_ai.client.token_budget.exceeded` Counter (incremented per
  breached bound) and `.utilization` Histogram (records `actual / budget` per declared bound).
- observability §11.3 — `openarmature.gen_ai.token_budget.kind = "input"` dimension.
- observability §11.4 — the utilization ratio is deterministic (fixed mock usage + declared budget),
  asserted as an exact value.

**Cases:**

1. `token_budget_input_exceeded_sets_attr_counter_and_utilization` — Budgeted prompt
   (`input_max_tokens: 10`, no total bound), mock usage `{prompt 20, completion 1, total 21}`,
   `enable_metrics = True`. `prompt_tokens` 20 > `input_max_tokens` 10, so the input bound is exceeded.
   The `LlmCompletionEvent.token_budget` carries `{input_max_tokens: 10, total_max_tokens: null}`; the
   span carries `openarmature.prompt.token_budget.input_max_tokens = 10` and
   `openarmature.llm.token_budget.exceeded = true`; the exceeded counter records once with
   `kind = "input"`; and a utilization observation is recorded at `20 / 10 = 2.0` with `kind = "input"`.

**Harness extensions:** uses the established `renders_prompt:`, `prompt_backend:`, and
`render_variables:` directives (fixtures 024 / 064) and `enable_metrics:` + the `metrics:` assertion
shape (fixtures 088–091). The prompt's `token_budget` object in `prompt_backend` is the
`{input_max_tokens, total_max_tokens}` config the backend surfaces on `Prompt.token_budget`
(prompt-management §3) — the same prompt-config slot fixture 013 uses for `sampling`; this proposal-0083
fixture is the first to populate it.

**What passes:**

- `LlmCompletionEvent.token_budget == {input_max_tokens: 10, total_max_tokens: null}` (the active
  prompt declared only the input bound).
- `openarmature.llm.token_budget.exceeded == true`; `openarmature.prompt.token_budget.input_max_tokens
  == 10`; `openarmature.prompt.token_budget.total_max_tokens` absent (the bound was not declared).
- The exceeded counter records exactly once, `kind = "input"`; the utilization histogram records `2.0`,
  `kind = "input"`.

**What fails:**

- `token_budget` is null on the completion event despite an active budgeted prompt (the binding didn't
  flow the budget through).
- `openarmature.llm.token_budget.exceeded` is false / absent despite `prompt_tokens > input_max_tokens`.
- The exceeded counter does not record, or records with the wrong `kind` (the per-bound detail lives on
  the `kind` dimension per §5.5.15).
- The utilization observation is missing, asserted with a comparison matcher rather than the exact `2.0`
  (§5.8 / §11.4 assert the exact value), or carries the wrong `kind`.
- A `total`-kind observation is recorded despite the prompt declaring no total bound.
