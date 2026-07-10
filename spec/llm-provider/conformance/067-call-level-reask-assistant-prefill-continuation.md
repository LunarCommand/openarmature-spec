# 067 — Call-level retry: reask with a caller assistant-prefill (continuation)

Verifies §7.1's **assistant-prefill continuation** branch of structured-output reask. When the
caller's `messages` end in an `assistant` message (a prefill), a reask retry does **not** start a new
`assistant` message for the model's attempt output — it **continues** the trailing assistant message,
concatenating the raw output onto that message's content **verbatim, with no OA-added separator** —
then appends the builder's `user` correction. This keeps the request role-alternating (§8.2 forbids
consecutive same-role messages) while OA authors none of its own text (charter §3.1 principle 7, *No
built-in prompts*).

The caller supplies `messages` ending in `{role: assistant, content: "Sure: "}`. Attempt 0 returns
`{"name":"Zoe"}` (missing the required `age` → `structured_output_invalid` per §7); the reask builder
makes it retryable. Because the working transcript's last message is already an `assistant` message,
attempt 1's request carries a **modified** caller message: the prefill `Sure: ` concatenated with the
attempt-0 output `{"name":"Zoe"}` verbatim → exactly `Sure: {"name":"Zoe"}`. Attempt 1 returns the
corrected object and the call succeeds.

Because a reask retry here **modifies** a caller message rather than only appending after it, attempt
1 is asserted via the full-list **`messages`** directive (conformance-adapter §5.11) — which asserts
the whole outbound message list, so it catches an implementation that starts a new `assistant`
message or inserts a delimiter. Attempt 0 (append-only, nothing appended) uses `appended_messages: []`.

**Spec sections exercised:**

- llm-provider §7.1 — Adaptive extensions: `reask` makes `structured_output_invalid` retryable for
  this call; on a `structured_output_invalid` attempt, when the working transcript's last message is
  already an `assistant` message (a caller prefill), the model's raw output **continues** that message
  — concatenated onto its content verbatim, with no OA-added separator — rather than starting a new
  `assistant` message, and the builder's returned content follows as a `user` message; the retry
  attempt carries `openarmature.llm.retry_reason = reask`. OA authors no prompt of its own (charter
  §3.1 principle 7).
- llm-provider §7 / proposal 0082 — the `structured_output_invalid` error surface the reask builder
  is fed (verbatim invalid `output_content`, failure description on `error_message`).
- conformance-adapter §5.11 — the full-list `messages` directive (used for attempt 1, because the
  reask modifies the caller's trailing assistant message rather than only appending), the
  `appended_messages` directive (attempt 0), and `attributes_absent` on the attempt-0 span.

**Cases:**

1. `reask_continues_assistant_prefill` — Caller `messages` end in `{role: assistant, content: "Sure: "}`;
   schema requires `[name, age]`. Attempt 0 returns `{"name":"Zoe"}` (missing `age`), attempt 1 returns
   `{"name":"Zoe","age":25}`. Asserts:
   - Attempt 0's wire request carries the caller's original messages — prefill included — unchanged
     (`appended_messages: []`).
   - Attempt 1's **full** outbound message list is exactly: the caller `user`; a single `assistant`
     message whose content is exactly `Sure: {"name":"Zoe"}` (prefill + attempt-0 output, concatenated
     verbatim, no separator); then the builder's `user` correction (asserted via `content_contains`,
     since the template interpolates the implementation-defined `{error_message}`).
   - The call returns the corrected, schema-valid `parsed` result.
   - Attempt 0 carries error category `structured_output_invalid` and no `retry_reason`; the retry
     carries `openarmature.llm.retry_reason = reask`.

**What passes:**

- A `structured_output_invalid` becomes retryable because a `reask` builder is present; the retry
  consumes a `max_attempts` attempt.
- The trailing assistant prefill is **continued** — attempt 1's request carries a single `assistant`
  message equal to `Sure: {"name":"Zoe"}` (prefill concatenated with the model's raw output, verbatim,
  no separator), followed by the `user` correction — proving OA neither starts a new assistant message,
  inserts a separator, nor authors any text of its own.
- The caller's original `messages` are unmutated (the continuation lives on an internal working
  transcript copy).
- The call returns the corrected `parsed` value; the reask retry carries `retry_reason = reask`.

**What fails:**

- `structured_output_invalid` raises on attempt 0 despite the `reask` builder — reask did not make
  it retryable.
- Attempt 0's wire request carries an appended or modified message — reask leaked onto the base attempt.
- Attempt 1's request starts a **new** `assistant` message (yielding two consecutive assistant
  messages) instead of continuing the prefill — breaks role-alternation.
- Attempt 1's continued assistant content inserts a separator (newline / delimiter) or otherwise
  differs from `Sure: {"name":"Zoe"}` — OA added text of its own beyond the prefill and the model's
  verbatim output.
- The caller's `messages` are mutated, or the retry attempt is missing `retry_reason = reask`.
