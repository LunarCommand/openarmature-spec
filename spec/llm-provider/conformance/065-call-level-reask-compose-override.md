# 065 — Call-level retry: reask composes with per-attempt override (accumulating transcript)

Verifies §7.1's statement that the two adaptive extensions **compose**, and that the reask working
transcript **accumulates** across retries. With both a `per_attempt_override` schedule and a `reask`
builder, each `structured_output_invalid` reask retry applies its scheduled sampling override *and*
appends the model's raw output plus the caller's corrective message. Attempt 0 returns
`{"name":"Dan"}` (missing `age`) and attempt 1 returns a *different* invalid output
`{"name":"Dan","age":"forty"}` (wrong type — still `structured_output_invalid`); attempt 2 returns
the corrected object. Because the two invalid outputs differ, attempt 2's transcript carries the
full four-message accumulation of both prior pairs, in order.

**Spec sections exercised:**

- llm-provider §7.1 — Adaptive extensions compose: `per_attempt_override` (attempt 0 base config;
  the *i*-th override on retry *i*) and `reask` (append the model's raw output as an `assistant`
  message then the builder's corrective message as a `user` message on `structured_output_invalid`)
  apply together on each reask retry. The working transcript starts as a copy of the caller's
  `messages` and accumulates each attempt's `(assistant output, user correction)` pair — so attempt
  2's request carries both prior pairs, keeping the sequence role-alternating. Retries carry
  `openarmature.llm.retry_reason = reask`.
- llm-provider §7 / proposal 0082 — the `structured_output_invalid` surface fed to the reask builder
  on each failing attempt.
- conformance-adapter §5.11 — combined `expected.wire_requests` assertions (`sampling` +
  `appended_messages` in a single entry, mixing exact `assistant` entries with `content_contains`
  `user` entries), and `attributes_absent` on the attempt-0 span.

**Cases:**

1. `override_and_reask_compose_and_accumulate` — Base `config = {temperature: 0.0}`, schedule
   `[{temperature: 0.3}, {temperature: 0.6}]`, reask template `"Correct {output_content}:
   {error_message}"`. Attempt 0 returns `{"name":"Dan"}`, attempt 1 returns
   `{"name":"Dan","age":"forty"}`, attempt 2 returns `{"name":"Dan","age":40}`. Asserts:
   - Attempt 0's wire request carries `temperature = 0.0` and nothing appended.
   - Attempt 1 (first reask retry) carries `temperature = 0.3` *and* appends attempt 0's pair: an
     `assistant` message equal to `{"name":"Dan"}` (exact) then a `user` correction containing
     `"Correct"` and `{"name":"Dan"}` (`content_contains`).
   - Attempt 2 (second reask retry) carries `temperature = 0.6` *and* appends the full four-message
     accumulation — attempt 0's pair followed by attempt 1's pair (`assistant`
     `{"name":"Dan","age":"forty"}` then a `user` correction containing `"Correct"` and
     `{"name":"Dan","age":"forty"}`), in order.
   - The call returns the corrected, schema-valid `parsed` result.
   - Attempt 0 carries no `retry_reason`; retries 1 and 2 carry `retry_reason = reask`.

**What passes:**

- Both extensions apply on the same reask retry — the scheduled override *and* the appended
  corrective pair appear together on the wire request.
- The transcript accumulates: attempt 2 carries both prior `(assistant output, user correction)`
  pairs in order, not just the most recent one.
- Attempt 0 stays on the base config with nothing appended; overrides target retries only.
- The call self-heals to the corrected `parsed` value; the caller's `messages` and `config` are
  unmutated; both reask retries carry `retry_reason = reask`.

**What fails:**

- A reask retry applies only one of the two behaviors (override without the appended pair, or the
  pair without the override) — the extensions did not compose.
- Attempt 2 carries only attempt 1's pair (the transcript was reset each retry instead of
  accumulating), or the pairs appear out of order or with the wrong role alternation.
- Attempt 0 carries an overridden temperature or an appended message.
- An appended `assistant` message differs from the model's raw output, or a `user` message contains
  OA-authored text beyond the rendered template.
- The caller's `messages` / `config` are mutated, or a reask retry is missing `retry_reason = reask`.
