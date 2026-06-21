# 116 — Call-level retry: one `call_id`, one node-level `attempt_index`

Verifies the §7.1-call-level-retry interaction with streaming (graph-engine §6, llm-provider §5 / §7.1): a streamed `complete(retry=...)` whose first wire attempt fails transiently and whose second succeeds is ONE call with ONE `call_id` and ONE node-level `attempt_index`. The wire retry does not advance the node-level index; exactly one terminal `LlmCompletionEvent` fires (no per-attempt typed event for the caught transient, per the one-typed-event-per-`complete()`-call mutual exclusion); and the assembled `Response` reflects the successful attempt only.

The transient wire attempt fails immediately (no content chunks precede the error), so it produces no partial token events — this isolates the `call_id` / `attempt_index` contract from the separate partial-replay behavior (proposal 0062's "Multi-attempt streams" note).

**Spec sections exercised:**

- llm-provider §7.1 — the call-level retry loop runs inside one `complete()` call; a caught transient does not raise, re-enter, or emit a per-attempt typed event.
- graph-engine §6 — `LlmTokenEvent.attempt_index` is node-level and does not vary across §7.1 wire attempts; one terminal typed event per `complete()` call; the token stream's `call_id` matches the terminal event's.

**Cases:**

1. `call_level_retry_token_events_share_one_call_id_and_attempt_index` — A `stream=True` node with `retry={max_attempts:2}`; wire attempt 0 is a transient `503` (caught internally), wire attempt 1 streams `"Re"`/`"try"`/`"ok"`. Asserts exactly three `LlmTokenEvent`s (the successful attempt's chunks only), all `attempt_index=0` and sharing one `call_id`; exactly one `LlmCompletionEvent` (`attempt_index=0`, same `call_id`, assembled content `"Retryok"`); and zero `LlmFailedEvent`.

**What passes:**

- All token events share one `call_id`, equal to the single terminal `LlmCompletionEvent`'s.
- All token events carry node-level `attempt_index=0` (the wire retry did not advance it).
- Exactly one `LlmCompletionEvent`; zero `LlmFailedEvent`; no per-attempt typed event for the caught transient.
- The assembled `Response` content reflects the successful attempt only.

**What fails:**

- Token events split across two `call_id`s, or carrying `attempt_index=1` for the post-retry attempt.
- A per-attempt typed event emitted for the caught transient (more than one terminal typed event).
- The assembled content carrying any artifact of the failed attempt.
