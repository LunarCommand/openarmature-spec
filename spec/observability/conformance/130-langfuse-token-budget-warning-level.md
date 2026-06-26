# 130 — Langfuse: token-budget exceedance sets generation level "WARNING"

Verifies observability §8.4.3's token-budget WARNING rule (per proposal 0083): on a token-budget
exceedance the bundled Langfuse observer SHOULD set the generation's `observation.level = "WARNING"`
with a `statusMessage` naming the exceeded bound, mapping the declared budget to
`generation.metadata.token_budget.*`. Runs fixture 126's input-exceeded case (a *successful* completion
whose `prompt_tokens` exceed the declared `input_max_tokens`) through the Langfuse observer.

The exceedance is advisory: the call succeeded, so the level is `WARNING`, not `ERROR` —
`token_budget` is observability-only and never fails the request (§5.5.15 / prompt-management §3).

**Spec sections exercised:**

- observability §8.4.3 — token-budget WARNING: `observation.level = "WARNING"` + a `statusMessage`
  naming the exceeded bound (the spec's example format `"token budget exceeded: input 1500 > 1000"`); the
  budget values map to `generation.metadata.token_budget.*`. SHOULD-level (the span attribute + §11
  metrics are MUST; the WARNING surfaces are SHOULD, §5.5.15).
- observability §5.5.15 — the over-budget evaluation that drives the WARNING (`prompt_tokens >
  input_max_tokens`).
- observability §8.4.4 — the prompt-identity `metadata.prompt` block still present (the active prompt).

**Cases:**

1. `langfuse_generation_warning_level_on_token_budget_exceed` — Budgeted prompt (`input_max_tokens: 10`)
   through the Langfuse observer, mock usage `{prompt 20, completion 1, total 21}`. `prompt_tokens` 20 >
   `input_max_tokens` 10. The Generation carries `level = "WARNING"`, `statusMessage = "token budget
   exceeded: input 20 > 10"`, and `metadata.token_budget.input_max_tokens = 10`, alongside the normal
   success rendering and the `metadata.prompt` identity block.

**Harness extensions:** combines `renders_prompt:` + the prompt's `token_budget` config with the
`langfuse_observer:` + `langfuse_trace:` assertion shape (fixtures 024 / 123).

**Precedence note (ERROR over WARNING):** §8.4.3 states a hard `ERROR`-level failure (§4.2 / §8.4.2)
takes precedence when both apply. This case is a clean success, so the WARNING stands. The combined case
— a `structured_output_invalid` failure (ERROR per §8.4.2) from a budgeted prompt over budget — would
render `level = "ERROR"` (the failure wins), with the budget still surfacing in
`metadata.token_budget.*`; fixture 131 exercises the metric/event side of that failure path, and the
ERROR-takes-precedence rendering is the §8.4.3 / §8.4.2 contract rather than a separate budget-WARNING
case.

**What passes:**

- `generation.level == "WARNING"` (not `ERROR` — the call succeeded).
- `generation.statusMessage` names the exceeded bound (`input`, with the actual vs. max values).
- `generation.metadata.token_budget.input_max_tokens == 10`; the `metadata.prompt` identity block
  present.

**What fails:**

- `level` is `ERROR` for a budget exceedance on a successful call (over-escalation — the budget is
  advisory, §5.5.15).
- `level` is unset / `DEFAULT` despite the exceedance (the SHOULD WARNING is dropped).
- `statusMessage` is absent or does not name which bound was exceeded.
- `metadata.token_budget.*` is missing (the budget values are not surfaced to the Langfuse UI).
