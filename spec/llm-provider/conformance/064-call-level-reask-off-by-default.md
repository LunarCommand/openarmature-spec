# 064 — Call-level retry: reask off by default

Verifies §7.1's **default (reask off)** behavior is preserved: absent a `reask` builder,
`structured_output_invalid` is non-transient and raises on its first occurrence — the retry loop
does not iterate, even with `max_attempts = 2`. Attempt 0 returns schema-invalid JSON (missing the
required `age`); the call raises immediately and the second mock response is never consumed.

**Spec sections exercised:**

- llm-provider §7.1 — Adaptive extensions: absent a `reask` builder, `structured_output_invalid`
  remains non-transient and raises on first occurrence (unchanged from §7); `max_attempts` does not
  trigger a retry for a non-transient category.
- llm-provider §7 / proposal 0082 — the raised `structured_output_invalid` error surface.
- conformance-adapter §5.11 — `expected.wire_requests` (`appended_messages: []`) proving exactly one
  attempt issued with nothing appended, and `attributes_absent` on the attempt-0 span.

**Cases:**

1. `structured_output_invalid_not_retried_without_reask` — Schema requires `[name, age]`; attempt 0
   returns `{"name":"Cara"}` (missing `age`); `retry = {max_attempts: 2}` with no `reask`. Asserts:
   - `complete()` raises `structured_output_invalid` on attempt 0 (no retry).
   - Exactly one wire request issues, carrying only the caller's original messages
     (`appended_messages: []`).
   - Exactly one LLM span emits (`attempt_index = 0`, no `retry_reason`).
   - The second mock response is never consumed — the loop did not iterate despite `max_attempts = 2`.

**What passes:**

- Without a `reask` builder, `structured_output_invalid` is non-transient and raises on the first
  failure — the pre-0095 default is preserved.
- Only one attempt issues; `max_attempts = 2` does not retry a non-transient category.
- The sole attempt appends nothing and its span carries no `retry_reason`.
- The second (deliberately valid) mock response is never requested.

**What fails:**

- The loop retries `structured_output_invalid` without a `reask` builder — reask defaulted on, or
  the classifier silently widened.
- More than one wire request / LLM span is produced, or the sole attempt appends a message.
- The call returns the second response's valid value — it must not have been consumed.
- A different error category is raised, or the error is missing its 0082 fields.
