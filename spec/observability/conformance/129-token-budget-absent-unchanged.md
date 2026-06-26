# 129 — Token budget: absent budget leaves the baseline unperturbed

Verifies observability §5.5.15 / §11.2 (per proposal 0083) on the no-budget baseline: when the active
prompt declares no `token_budget`, the entire token-budget surface is inert — the
`LlmCompletionEvent.token_budget` field is null, no `openarmature.*.token_budget.*` span attributes
appear, and neither §11.2 token-budget instrument records. `enable_metrics` is on, so the ordinary §11
token-usage and duration instruments still record (fixture 088), proving proposal 0083 perturbs nothing
when no budget is declared — the new signals are gated on a declared budget, not on the proposal being
present.

**Spec sections exercised:**

- graph-engine §6 — `LlmCompletionEvent.token_budget` is null when the active prompt declared no budget.
- observability §5.5.15 — the `openarmature.prompt.token_budget.*` attributes are emitted only when the
  bound is declared; `openarmature.llm.token_budget.exceeded` only when a budget exists — so all three
  are absent here.
- observability §11.2 — the token-budget instruments record only on a budgeted call ("every call with
  that bound declared"); with no budget, neither records. The token-usage / duration instruments are
  unaffected (fixture 088).

**Cases:**

1. `token_budget_absent_leaves_baseline_unperturbed` — Prompt with no `token_budget`, mock usage
   `{prompt 5, completion 1, total 6}`, `enable_metrics = True`. `LlmCompletionEvent.token_budget` is
   null; `active_prompt` is still populated (the identity surface is independent of the budget surface);
   no `openarmature.*.token_budget.*` span attributes; the token-usage (5 / 1) and duration observations
   still record; neither token-budget instrument records.

**Harness extensions:** same directives as fixtures 126–128, but the prompt in `prompt_backend` carries
**no** `token_budget` object — the contrast that isolates the budget surface from the always-present
`active_prompt` identity surface.

**Harness note (absence assertion):** as in fixture 128, the absence of token-budget *metric*
observations (amid the token-usage / duration observations that the `metrics:` list does assert) is
expressed as the fixture-specific invariant `no_token_budget_instrument_observations_when_no_budget`
(§5.9) — the `metrics:` directive asserts recorded observations and has no per-instrument absence form
short of `metrics: []`, which would wrongly demand zero token-usage observations too. The absent span
attributes use the established `attributes_absent:` directive (fixtures 012 / 124).

**What passes:**

- `LlmCompletionEvent.token_budget == null`; `active_prompt` populated as usual.
- None of `openarmature.prompt.token_budget.input_max_tokens` / `.total_max_tokens` /
  `openarmature.llm.token_budget.exceeded` present on the span.
- Token-usage observations (5 / `"input"`, 1 / `"output"`) and one duration observation record; neither
  token-budget instrument records.

**What fails:**

- `openarmature.llm.token_budget.exceeded` is emitted (e.g. as `false`) despite no declared budget — the
  attribute is gated on a budget existing, not on metrics being on.
- A `token_budget.utilization` observation is recorded with no budget to divide by (a divide-by-absent
  defect).
- The token-usage or duration observations stop recording when no budget is declared — proposal 0083
  perturbed the baseline path.
- `LlmCompletionEvent.token_budget` is a zero / empty record rather than null.
