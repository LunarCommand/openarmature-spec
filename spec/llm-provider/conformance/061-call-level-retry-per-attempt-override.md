# 061 — Call-level retry: per-attempt request override

Verifies §7.1's adaptive **per-attempt request override**: a `complete()` call with a `retry`
carrying a `per_attempt_override` schedule varies the outbound request's sampling across retries
while leaving attempt 0 on the caller's base `config`. Attempt 0 and attempt 1 (the first retry)
fail transiently (HTTP 503 → `provider_unavailable`); attempt 2 (the second retry) succeeds. No
reask builder is supplied, so nothing is appended to the working transcript on any attempt. Three
LLM spans emit; the retry attempts carry `openarmature.llm.retry_reason = transient` per §7.1.

**Spec sections exercised:**

- llm-provider §7.1 — Adaptive extensions: `per_attempt_override` retry schedule (attempt 0 uses
  the base `config` unmodified; the *i*-th override applies to retry *i* (attempt *i+1*), merged
  onto base), the `complete()` no-mutate-`config` contract, and the per-attempt
  `openarmature.llm.retry_reason` attribute on retry attempts (present on every retry, including a
  successful final retry; absent on attempt 0).
- conformance-adapter §5.11 — `call.retry.per_attempt_override` directive; the per-attempt
  `expected.wire_requests` outbound-request assertion (`sampling`, plus `appended_messages: []`
  asserting no reask append); and `attributes_absent` on the attempt-0 span asserting it carries no
  `retry_reason`.

**Cases:**

1. `per_attempt_override_applies_to_retries_only` — Base `config = {temperature: 0.0}`, schedule
   `[{temperature: 0.3}, {temperature: 0.6}]`. Provider returns 503 on attempts 0 and 1, then 200.
   Asserts:
   - Attempt 0's wire request carries `temperature = 0.0` (the base config, unmodified) and nothing
     appended.
   - Attempt 1 (first retry) carries `temperature = 0.3` (override[0] merged onto base).
   - Attempt 2 (second retry) carries `temperature = 0.6` (override[1] merged onto base).
   - The call returns the successful response.
   - Attempts 1 and 2 carry `openarmature.llm.retry_reason = transient`; attempt 0 carries none.

**What passes:**

- Attempt 0 uses the caller's base sampling; each retry applies its scheduled override to the wire
  request — the override schedule targets retries, not the base attempt.
- The caller's `config` is not mutated (overrides are applied to per-attempt copies).
- Three per-attempt LLM spans emit; retry attempts carry `retry_reason = transient` (including the
  successful attempt 2), and attempt 0's span carries no `retry_reason`.

**What fails:**

- Attempt 0's wire request carries an overridden temperature — the schedule leaked onto the base
  attempt (off-by-one; the base is not part of the schedule).
- A retry's wire request carries the base temperature — the override was not applied.
- Any attempt appends a message — there is no reask builder, so `appended_messages` must be empty.
- The caller's `config` is mutated in place.
- A retry attempt is missing `openarmature.llm.retry_reason`, or attempt 0 carries one.
