# 062 — Call-level retry: structured-output reask corrected on retry

Verifies §7.1's **structured-output reask**: with a `reask` builder supplied, `complete()` treats a
`structured_output_invalid` on attempt 0 as retryable *for this call*, appends the model's raw
output plus the caller's corrective message to the next attempt, and returns the corrected result.
Attempt 0 returns valid JSON missing the required `age` field (→ `structured_output_invalid` per
§7); attempt 1 returns the corrected object and the call succeeds.

This is the **exactness** fixture. The reask template is `{output_content}`-only (deterministic — no
`{error_message}` interpolation), so both appended messages are asserted by exact content: the
`assistant` message is exactly the model's raw attempt-0 output, and the `user` message is exactly
the builder's rendering. Together they prove OA appends the model output plus the builder's
rendering and nothing OA-authored (charter §3.1 principle 7, *No built-in prompts*).

**Spec sections exercised:**

- llm-provider §7.1 — Adaptive extensions: `reask` makes `structured_output_invalid` retryable for
  this call (no custom classifier), reask attempts consume the `max_attempts` budget, the builder
  receives the raised error's 0082 surface (`output_content` + `error_message`), on a
  `structured_output_invalid` attempt OA appends the model's own raw output as an `assistant`
  message then the builder's returned content as a `user` message (authoring no prompt of its own),
  and the retry attempt carries `openarmature.llm.retry_reason = reask`.
- llm-provider §7 / proposal 0082 — the `structured_output_invalid` error surface the reask builder
  is fed (verbatim invalid `output_content`, failure description on `error_message`).
- conformance-adapter §5.11 — `call.retry.reask.template` directive, the per-attempt
  `expected.wire_requests` assertion (`appended_messages` with exact `{role, content}` pairs), and
  `attributes_absent` on the attempt-0 span.

**Cases:**

1. `reask_corrects_structured_output_invalid` — Schema requires `[name, age]`; attempt 0 returns
   `{"name":"Alice"}` (missing `age`), attempt 1 returns `{"name":"Alice","age":30}`. Asserts:
   - Attempt 0's wire request carries only the caller's original messages (`appended_messages: []`).
   - The reask retry appends exactly two messages: an `assistant` message equal to the model's raw
     attempt-0 output (`{"name":"Alice"}`), then a `user` message equal to the builder's rendered
     correction — both by exact content, with no OA-authored prompt.
   - The call returns the corrected, schema-valid `parsed` result.
   - Attempt 0 carries error category `structured_output_invalid` and no `retry_reason`; the retry
     carries `openarmature.llm.retry_reason = reask`.

**What passes:**

- A `structured_output_invalid` becomes retryable because a `reask` builder is present (no custom
  classifier needed); the retry consumes a `max_attempts` attempt.
- The appended `assistant` message is exactly the model's raw output and the appended `user` message
  is exactly the builder's rendering — proving OA adds no prompt of its own.
- The caller's original `messages` are unmutated (the appended pair lives on an internal working
  transcript copy).
- The call returns the corrected `parsed` value; the reask retry carries `retry_reason = reask`.

**What fails:**

- `structured_output_invalid` raises on attempt 0 despite the `reask` builder — reask did not make
  it retryable.
- Attempt 0's wire request carries an appended message — reask leaked onto the base attempt.
- The reask retry appends only one message, appends them out of order, or the appended text differs
  from the model's output / the builder's rendering (or contains OA-authored text) — violates the
  role-alternating no-hidden-prompt contract.
- The caller's `messages` are mutated, or the retry attempt is missing `retry_reason = reask`.
