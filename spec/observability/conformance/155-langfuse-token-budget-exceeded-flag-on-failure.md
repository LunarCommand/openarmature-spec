# 155 — Langfuse `token_budget_exceeded` flag survives ERROR precedence (failure path)

Pins proposal 0109's §8.4.3 addition: on an over-budget `structured_output_invalid` **failure**, the Langfuse
failed Generation renders `ERROR` (the failure wins the level / statusMessage), but the exceedance stays
discoverable via a `generation.metadata.token_budget_exceeded = true` flag emitted **regardless of level** — the
Langfuse-side parity for the OTel `openarmature.llm.token_budget.exceeded` attribute that fixture 131 asserts on
the OTel span. Without it, an operator triaging the failure in Langfuse could see the declared budget but not
that the call was also over it.

Setup mirrors fixture 131 case 1 (a budgeted prompt whose failed call's usage exceeds the bound — the
`structured_output_invalid` category carries usage, per 0082, so the budget evaluates on the failure) driven
through the Langfuse observer (123 / 130 dialect).

**Spec sections exercised:**

- observability §8.4.3 (proposal 0109) — `generation.metadata.token_budget_exceeded`, a flat sibling boolean set
  regardless of `observation.level`, so it survives the ERROR-precedence rule.
- observability §8.4.2 — the failed Generation still renders `ERROR` + the `structured_output_invalid`
  statusMessage (unchanged); the declared bounds stay on `metadata.token_budget.*`.

**Case:**

1. `over_budget_structured_output_failure_langfuse_exceeded_flag_survives_error` — `input_max_tokens 10`, failed
   call `prompt_tokens 20`: the failed Generation is `ERROR` / `"structured_output_invalid"` **and**
   `metadata.token_budget_exceeded = true` alongside `metadata.token_budget.input_max_tokens = 10`.

**What fails:**

- Suppressing the exceedance on the failure path (the flag absent because ERROR "won"), emitting it as a nested
  field under `token_budget` rather than the flat sibling, or changing the ERROR level / category.
