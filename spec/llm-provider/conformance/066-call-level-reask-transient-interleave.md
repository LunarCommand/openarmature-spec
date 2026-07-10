# 066 — Call-level retry: transient failure interleaved in a reask loop

Verifies §7.1's handling of a **transient failure interleaved inside a reask-enabled loop**: a
single `complete()` call whose retry loop mixes a structured-output reask and a transient retry, and
whose per-attempt `retry_reason` distinguishes the two causes. With a `reask` builder supplied (and
**no** `per_attempt_override`), attempt 0 returns valid JSON missing the required `age` field (→
`structured_output_invalid` per §7), which the builder makes retryable for this call. Attempt 1 (the
reask retry) carries attempt 0's corrective pair on its request but returns HTTP 503 (→
`provider_unavailable`, transient). Attempt 2 (the transient retry) re-sends the **same** accumulated
transcript — a transient retry appends no new reask pair — and returns the corrected object, so the
call succeeds.

This is the **interleave** fixture. Its two load-bearing assertions are that a transient retry
carries the accumulated reask transcript through unchanged (attempt 2's `appended_messages` equal
attempt 1's), and that `retry_reason` discriminates the two retry causes in one loop: attempt 1
retried attempt 0's `structured_output_invalid` (`retry_reason = reask`) even though attempt 1 itself
failed transient, and attempt 2 retried attempt 1's 503 (`retry_reason = transient`). The user
corrections are asserted via `content_contains` because the reask template interpolates the
implementation-defined `{error_message}`; the assistant output is asserted by exact content (the
verbatim model output).

**Spec sections exercised:**

- llm-provider §7.1 — Adaptive extensions: `reask` makes `structured_output_invalid` retryable for
  this call, and a **transient** retry interleaved in a reask-enabled loop appends no reask pair but
  re-sends the working transcript accumulated so far. The per-attempt `openarmature.llm.retry_reason`
  records why **this** attempt occurred — the prior failure's class — so a reask retry that itself
  fails transient still carries `retry_reason = reask`, and the transient retry that follows carries
  `retry_reason = transient`. Attempt 0 carries no `retry_reason`. N attempts emit N LLM spans.
- llm-provider §7 / proposal 0082 — the `structured_output_invalid` error surface (verbatim invalid
  `output_content`, failure description on `error_message`) the reask builder is fed.
- conformance-adapter §5.11 — the `call.retry.reask.template` directive, the per-attempt
  `expected.wire_requests` assertion (`appended_messages` with exact `{role, content}` pairs and
  `content_contains` substring sets), and `attributes_absent` on the attempt-0 span.

**Cases:**

1. `transient_reask_interleave` — Schema requires `[name, age]`; attempt 0 returns `{"name":"Eve"}`
   (missing `age`, → `structured_output_invalid`), attempt 1 returns HTTP 503 (→
   `provider_unavailable`), attempt 2 returns `{"name":"Eve","age":50}`. Asserts:
   - Attempt 0's wire request carries only the caller's original messages (`appended_messages: []`).
   - Attempt 1's wire request appends attempt 0's corrective pair: an `assistant` message equal to
     the model's raw attempt-0 output (`{"name":"Eve"}`), then a `user` message whose text contains
     the template literal `Fix` and the verbatim `{"name":"Eve"}` output.
   - Attempt 2's wire request appends the **same** two messages as attempt 1 — the transient retry
     carries the accumulated reask transcript through and appends nothing new.
   - The call returns the corrected, schema-valid `parsed` result.
   - Attempt 0 carries error category `structured_output_invalid` and no `retry_reason`; attempt 1
     carries `openarmature.llm.retry_reason = reask` and error category `provider_unavailable`;
     attempt 2 carries `openarmature.llm.retry_reason = transient` and no error category.

**What passes:**

- A `structured_output_invalid` becomes retryable because a `reask` builder is present; the transient
  503 on the reask retry is retried by the default classifier; both consume the `max_attempts`
  budget.
- The transient retry (attempt 2) re-sends the exact accumulated transcript from the reask retry
  (attempt 1) and appends no new reask pair — the appended-message lists are identical.
- `retry_reason` records the prior failure's class per attempt: attempt 1 = `reask` (retried attempt
  0's structured-output failure) even though attempt 1 failed transient; attempt 2 = `transient`
  (retried attempt 1's 503).
- The call returns the corrected `parsed` value; three attempts emit three LLM spans; the caller's
  original `messages` are unmutated.

**What fails:**

- The transient retry (attempt 2) drops or re-derives the accumulated reask transcript, appends a
  fresh reask pair for the 503, or its `appended_messages` differ from attempt 1's — violates the
  "transient retry carries the accumulated transcript, appends nothing new" contract.
- Attempt 1 carries `retry_reason = transient` instead of `reask` (records its own failure class
  rather than the prior attempt's), or attempt 2 carries `reask` instead of `transient` — the two
  retry causes are not discriminated.
- The reask does not make `structured_output_invalid` retryable, or the 503 is not retried; the call
  raises instead of returning the corrected result.
- Attempt 0 carries a `retry_reason`, or its wire request carries an appended message; the caller's
  `messages` are mutated; or fewer than three LLM spans emit.
