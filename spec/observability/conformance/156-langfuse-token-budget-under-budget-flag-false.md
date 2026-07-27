# 156 — Langfuse `token_budget_exceeded` present-and-`false` under budget

Pins the within-budget arm of §8.4.3's flag rule (proposal 0109): the observer emits
`generation.metadata.token_budget_exceeded` as `true` **or** `false` whenever a budget is declared and at least
one bound is evaluable — so on an under-budget successful call the flag is **present and `false`**, not omitted.
This blocks an implementation that only sets the flag when a budget is exceeded (leaving the common within-budget
path with the flag absent). Fixtures 130 (WARNING path) and 155 (failure path) cover `true`; fixture 128 covers
the OTel `false` span attribute; this covers the Langfuse `false` metadata flag.

**Spec sections exercised:**

- observability §8.4.3 (proposal 0109) — `metadata.token_budget_exceeded` emitted `true`/`false` on any
  budget-declared, bound-evaluable call; here `false` on an under-budget success, with no WARNING level.
- observability §5.5.15 — the over-budget evaluation (`prompt_tokens 20 < input_max_tokens 40` → not exceeded).

**Case:**

1. `langfuse_generation_under_budget_exceeded_flag_false` — budgeted prompt (`input_max_tokens 40`), successful
   call with usage 20: the Generation renders as a normal success (no WARNING) and carries
   `metadata.token_budget_exceeded = false` alongside `metadata.token_budget.input_max_tokens = 40`.

**What fails:**

- Omitting the flag on the within-budget path (present-and-`false` is the contract, not absent), or emitting a
  WARNING level / statusMessage when nothing was exceeded.
