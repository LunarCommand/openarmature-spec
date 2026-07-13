# 063 — Call-level retry: structured-output reask budget exhausted

Verifies §7.1's **reask budget** semantics: reask attempts consume the same `max_attempts` budget
(there is no separate reask budget), and when the budget is exhausted with every attempt still
invalid, the final `structured_output_invalid` propagates to the caller. Both attempts return
schema-invalid JSON (missing the required `age` field).

**Spec sections exercised:**

- llm-provider §7.1 — Adaptive extensions: `reask` retries consume the `max_attempts` budget; on a
  `structured_output_invalid` the loop appends the model's raw output as an `assistant` message then
  the builder's rendered correction as a `user` message; on exhaustion the final error propagates
  per the normal `complete()` exception path; the retry attempt carries
  `openarmature.llm.retry_reason = reask`; the final-error category lands on the last attempt's span.
- llm-provider §7 / proposal 0082 — the propagated `structured_output_invalid` error surface
  (`response_schema` present, `output_content`, `error_message`, `finish_reason`, `usage`).
- conformance-adapter §5.11 — `call.retry.reask.template` directive, the per-attempt
  `expected.wire_requests` assertion (`appended_messages` mixing an exact `assistant` entry with a
  `content_contains` `user` entry), and `attributes_absent` on the attempt-0 span.

**Cases:**

1. `reask_budget_exhausted_propagates` — `max_attempts = 2`; attempt 0 and the reask retry both
   return `{"name":"Bob"}` (missing `age`). Asserts:
   - Two attempts issue (attempt 0 + one reask retry), consuming the `max_attempts` budget.
   - Attempt 0 appends nothing; the reask retry appends the model's raw output as an `assistant`
     message (exact `{"name":"Bob"}`) and the builder's correction as a `user` message, asserted via
     `content_contains` (`"Fix"`, `{"name":"Bob"}`) because the template interpolates the
     implementation-defined `{error_message}`.
   - After the budget is exhausted, `complete()` raises `structured_output_invalid` carrying the
     last attempt's 0082 error surface.
   - Attempt 0 carries no `retry_reason`; the retry carries `retry_reason = reask`.

**What passes:**

- Reask retries draw down the shared `max_attempts` budget rather than a separate reask budget.
- On exhaustion, the final `structured_output_invalid` propagates to the caller with its 0082
  surface (including `finish_reason` and `usage`).
- Two per-attempt LLM spans emit; attempt 0 carries no `retry_reason` and the retry carries
  `retry_reason = reask`.

**What fails:**

- The loop issues more than `max_attempts` attempts — reask added a separate budget.
- The call returns normally, or raises a different category, instead of propagating the final
  `structured_output_invalid`.
- The reask retry fails to append the model's raw `assistant` output before the `user` correction,
  or the propagated error is missing its required 0082 fields (`finish_reason` / `usage`).
- The retry attempt is missing `retry_reason = reask`.
