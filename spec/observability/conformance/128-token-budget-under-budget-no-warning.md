# 128 — Token budget: under budget records utilization, no exceeded warning

Verifies observability §5.5.15 / §11.2 (per proposal 0083) on the under-budget case: an active prompt
declares a `token_budget` the call's usage stays under. No bound is exceeded, so
`openarmature.llm.token_budget.exceeded` is `false` and the exceeded counter records nothing — **but**
the utilization histogram still records the under-budget ratio, because §11.2 records it on every
budgeted call ("exceeded or not"), so the distribution shows how close prompts run to budget. This is
the baseline-of-the-signal case: a budget that is observed but not breached.

**Spec sections exercised:**

- graph-engine §6 — `LlmCompletionEvent.token_budget` field (proposal 0083).
- observability §5.5.15 — `openarmature.prompt.token_budget.input_max_tokens` (the declared bound, still
  emitted) and `openarmature.llm.token_budget.exceeded = false` (no bound crossed; the attribute is
  emitted as `false`, not omitted, because a budget was declared).
- observability §11.2 — the `.utilization` Histogram records on every budgeted call regardless of
  outcome; the `.exceeded` Counter increments only per breached bound (so it records nothing here).
- observability §11.4 — the under-budget ratio `0.5` is deterministic, asserted as an exact value.

**Cases:**

1. `token_budget_under_budget_records_utilization_no_exceeded` — Budgeted prompt
   (`input_max_tokens: 40`, no total bound), mock usage `{prompt 20, completion 1, total 21}`,
   `enable_metrics = True`. `prompt_tokens` 20 <= `input_max_tokens` 40, so no bound is exceeded. The
   span carries `openarmature.prompt.token_budget.input_max_tokens = 40` and
   `openarmature.llm.token_budget.exceeded = false`; the utilization histogram records `20 / 40 = 0.5`
   with `kind = "input"`; the exceeded counter records nothing.

**Harness extensions:** same as fixtures 126 / 127 (`renders_prompt:` + the prompt's `token_budget`
config, `enable_metrics:`, the `metrics:` assertion shape).

**Harness note (absence assertion):** the `metrics:` expected-outcome directive (conformance-adapter
§5.8) asserts each *recorded* observation; its only documented whole-set form is `metrics: []` (the
`enable_metrics`-off gate). "The exceeded counter recorded no observation, while a utilization
observation *was* recorded" is therefore expressed as the fixture-specific invariant
`no_token_budget_exceeded_observation_when_under_budget` (per §5.9, fixture-specific predicates are
documented in the originating fixture's prose) — it is a genuine absence predicate over the captured
measurement set, not a restatement of the `exceeded = false` span-attribute assertion.

**What passes:**

- `openarmature.llm.token_budget.exceeded == false`; `openarmature.prompt.token_budget.input_max_tokens
  == 40` present.
- The utilization histogram records `0.5`, `kind = "input"`.
- No `openarmature.gen_ai.client.token_budget.exceeded` observation is recorded.

**What fails:**

- `openarmature.llm.token_budget.exceeded` is `true` despite usage under the bound (a comparison sense
  defect, e.g. `>=` instead of `>` at the boundary, or an off-by-one).
- The exceeded counter records an observation despite no bound being breached.
- No utilization observation is recorded under budget — the impl only records utilization on exceedance,
  collapsing the distribution to its over-budget tail (the histogram's sub-`1.0` distribution is its
  point, §11.2).
- The utilization value is asserted with a comparison matcher rather than the exact `0.5`.
- `openarmature.llm.token_budget.exceeded` is omitted (absent) rather than emitted as `false` — the
  attribute is emitted whenever a budget was declared (§5.5.15).
