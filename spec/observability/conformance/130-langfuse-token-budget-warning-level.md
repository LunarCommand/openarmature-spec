# 130 — Langfuse: token-budget exceedance sets generation level "WARNING"

Verifies observability §8.4.3's token-budget WARNING rule (per proposal 0083): on a token-budget
exceedance the bundled Langfuse observer SHOULD set the generation's `observation.level = "WARNING"`
with a `statusMessage`, and maps the declared budget to `generation.metadata.token_budget.*`. Runs
fixture 126's input-exceeded case (a *successful* completion whose `prompt_tokens` exceed the declared
`input_max_tokens`) through the Langfuse observer. The WARNING level is a SHOULD, so the case that
asserts it is gated on the `langfuse_token_budget_warning_level` capability. The token-budget metadata
is asserted ungated, on the same inputs.

The exceedance is advisory: the call succeeded, so the level is `WARNING`, not `ERROR` —
`token_budget` is observability-only and never fails the request (§5.5.15 / prompt-management §3).

**Spec sections exercised:**

- observability §8.4.3: the token-budget WARNING, `observation.level = "WARNING"` with a
  `statusMessage`. The spec's example message, `"token budget exceeded: input 1500 > 1000"`, names the
  exceeded bound; its text is only an example. The budget values map to
  `generation.metadata.token_budget.*`. SHOULD-level (the span attribute + §11 metrics are MUST; the
  WARNING surfaces are SHOULD, §5.5.15). Per proposal 0109 the observer also sets the flat
  `metadata.token_budget_exceeded` boolean regardless of level (MUST).
- observability §5.5.15 — the over-budget evaluation that drives the WARNING (`prompt_tokens >
  input_max_tokens`).
- observability §8.4.4 — the prompt-identity `metadata.prompt` block still present (the active prompt).
- conformance-adapter §5.17: the `requires_capability` gate on case 2. The
  `langfuse_token_budget_warning_level` capability is defined in this directory's harness note.

**Cases:**

1. `langfuse_generation_token_budget_metadata_on_exceed`: budgeted prompt (`input_max_tokens: 10`)
   through the Langfuse observer, mock usage `{prompt 20, completion 1, total 21}`. `prompt_tokens` 20 >
   `input_max_tokens` 10. Ungated. The Generation carries `metadata.token_budget.input_max_tokens = 10`
   and, per proposal 0109, the flat `metadata.token_budget_exceeded = true` flag, alongside the normal
   success rendering and the `metadata.prompt` identity block.
2. `langfuse_generation_warning_level_on_token_budget_exceed`: case 1's inputs, gated on
   `langfuse_token_budget_warning_level: true`. The Generation carries `level = "WARNING"` and a
   non-empty `statusMessage` (`"<any-string>"`). §8.4.3 gives the message's text only as an example, so
   its wording is not asserted.

**Harness extensions:** combines `renders_prompt:` + the prompt's `token_budget` config with the
`langfuse_observer:` + `langfuse_trace:` assertion shape (fixtures 024 / 123).

**Precedence note (ERROR over WARNING):** §8.4.3 states a hard `ERROR`-level failure (§4.2 / §8.4.2)
takes precedence when both apply. These cases are a clean success, so the WARNING stands. The combined case
— a `structured_output_invalid` failure (ERROR per §8.4.2) from a budgeted prompt over budget — renders
`level = "ERROR"` (the failure wins the level / statusMessage), with the budget still on
`metadata.token_budget.*` **and** the `metadata.token_budget_exceeded` flag surviving ERROR precedence
(proposal 0109). Fixture 131 exercises the OTel metric/event side of that failure path, and fixture 155
the Langfuse exceeded-flag side.

**What passes:**

- Case 1: `generation.metadata.token_budget.input_max_tokens == 10` and
  `generation.metadata.token_budget_exceeded == true`; the `metadata.prompt` identity block present.
- Case 2: `generation.level == "WARNING"` (not `ERROR`: the call succeeded) and a non-empty
  `generation.statusMessage`.

**What fails:**

- `level` is `ERROR` for a budget exceedance on a successful call (over-escalation — the budget is
  advisory, §5.5.15).
- `level` is unset / `DEFAULT` despite the exceedance (the SHOULD WARNING is dropped).
- `statusMessage` is absent or empty.
- `metadata.token_budget.*` or the `metadata.token_budget_exceeded` flag is missing (the budget values
  are not surfaced to the Langfuse UI).

Case 2 catches the first three, for an adapter that declares the capability. Case 1 catches the last.
