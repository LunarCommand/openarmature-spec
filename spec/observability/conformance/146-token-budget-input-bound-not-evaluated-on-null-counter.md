# 146 — Token-budget bound not evaluated on a not-reported counter

Verifies observability §5.5.15 / §11.2's **not-evaluated** rule for the 0083 token-budget instruments
and span signal (per proposal 0101): a bound whose actual counter is not reported is **not evaluated** —
no `openarmature.gen_ai.client.token_budget.utilization` observation, no
`openarmature.gen_ai.client.token_budget.exceeded` increment, and the `openarmature.llm.token_budget.exceeded`
span signal is not set for it. A comparison or ratio against a null is **undefined — not `false` / `0`**.
This closes the null-comparison leak in the 0083 reactive over-budget signal, which read
`usage.prompt_tokens > input_max_tokens` (a null comparison) before this proposal.

Both cases use a not-reported `prompt_tokens` — mock usage `{prompt_tokens: null, ...}`, the `{null,
...}` record of 0101 (malformed `prompt_tokens` nulled per llm-provider §7 *Malformed usage counter*).
The wire carries `prompt_tokens: null` directly (the post-nulling state); these fixtures render a null
counter, they do not test the wire-malformed → `null` mapping (sibling llm-provider fixture).

**Spec sections exercised:**

- observability §5.5.15 — the `openarmature.llm.token_budget.exceeded` span signal follows the §11.2
  not-evaluated rule; a bound whose counter is not reported does not set it.
- observability §11.2 — the token-budget instruments do not evaluate a bound whose counter is not
  reported (no `utilization` observation, no `exceeded` increment). The declared-budget span attributes
  still surface.
- graph-engine §6 (proposal 0101) — `LlmCompletionEvent.usage` mirrors the response: a present record
  with a null counter, not a null record.
- llm-provider §7 *Malformed usage counter* — a malformed counter is not reported.

**Cases:**

1. `input_only_budget_not_evaluated_and_exceeded_signal_absent_when_prompt_tokens_null` — a prompt
   declaring **only** `input_max_tokens` (10), mock usage `{null, 5, 15}`. The only declared bound is
   unevaluable. Asserts: the declared `openarmature.prompt.token_budget.input_max_tokens` = 10 still
   surfaces; `openarmature.llm.token_budget.exceeded` is **absent** (not set — **not** `false`); neither
   token-budget instrument records; the baseline `token.usage` `"output"` observation + duration still
   record; the event mirrors `usage.prompt_tokens = null`. This pins the not-`false`/not-`0` rule.

2. `input_bound_skipped_total_bound_still_evaluated_independence` — a prompt declaring **both**
   `input_max_tokens` (10) and `total_max_tokens` (8), mock usage `{null, 5, 12}`. The input bound's
   counter is null (not evaluated); the total bound's counter is sound and exceeded (12 > 8). Asserts:
   both declared budgets surface; `openarmature.llm.token_budget.exceeded` = `true` (the surviving total
   bound sets the aggregate signal); the `token_budget.exceeded` counter records once with kind
   `"total"` **only** (no `"input"` increment); `token_budget.utilization` records 12 / 8 = 1.5 with kind
   `"total"` **only**. This pins **independence** — the null input counter suppresses only the input
   bound.

**What passes:**

- Case 1: no budget instrument records; the exceeded span attribute is absent (not `false`).
- Case 2: only the total-kind budget observations record; the input bound is silent; the aggregate
  exceeded span signal is `true` from the total bound.

**What fails:**

- A `token_budget.utilization` observation recorded from `prompt_tokens / input_max_tokens` over a null
  `prompt_tokens` (undefined ratio).
- A `token_budget.exceeded` increment with kind `"input"` from a null comparison.
- Case 1: `openarmature.llm.token_budget.exceeded` emitted as `false` (treating not-evaluated as
  under-budget) — the exact per-record confusion 0101 forbids.
- Case 2: the total bound not evaluated (the null input counter wrongly suppressing the whole call's
  budget evaluation).
