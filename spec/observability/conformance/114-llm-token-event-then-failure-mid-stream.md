# 114 — Partial token events then `LlmFailedEvent` on mid-stream failure

Verifies graph-engine §6's unpaired-token-event contract: a streamed `complete()` call that fails mid-stream emits the partial `LlmTokenEvent`s it produced, then the terminal `LlmFailedEvent` (proposal 0058) — there is no `LlmTokenFailedEvent`. The §7 category exception still raises out of `complete()`. The call's outcome is carried by the terminal failure event, never by the token events.

**Spec sections exercised:**

- graph-engine §6 — `LlmTokenEvent` is unpaired (no `LlmTokenFailedEvent`); a mid-stream failure emits the partial token events then the terminal `LlmFailedEvent`.
- llm-provider §7 — the category exception (`provider_unavailable`) raises out of `complete()`.

**Cases:**

1. `partial_token_events_then_failed_event_no_token_failed_event` — A `stream=True` call whose mock yields content chunks `"Par"` / `"tial "` then a mid-stream failure marker (`503` → `provider_unavailable`). Asserts the two partial `LlmTokenEvent`s (`delta_kind="content"`, `chunk_index` `0,1`), exactly one `LlmFailedEvent` (`error_category="provider_unavailable"`), zero `LlmCompletionEvent`, zero events of any `LlmTokenFailedEvent` kind, and that the exception propagates out of `complete()`.

**What passes:**

- The partial token events fire (in `chunk_index` order) before the failure surfaces.
- Exactly one terminal `LlmFailedEvent`; zero `LlmCompletionEvent`.
- No paired token-failure variant is emitted.
- The `provider_unavailable` exception raises out of the call.

**What fails:**

- An `LlmCompletionEvent` emitted for the failed streamed call.
- A paired `LlmTokenFailedEvent` (or equivalent) emitted.
- The exception swallowed (no raise) after a mid-stream error.
