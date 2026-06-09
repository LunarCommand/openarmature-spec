# 072 — Mutual exclusion: `LlmFailedEvent` and `LlmCompletionEvent` per call

Verifies graph-engine §6's mutual-exclusion rule (per proposal 0058) — implementations MUST
NOT emit both `LlmFailedEvent` and `LlmCompletionEvent` for the same `provider.complete()`
call. Dedicated lockdown fixture so an implementation that emits both for the same failed
call fails this fixture explicitly.

**Spec sections exercised:**

- graph-engine §6 — *LLM failure event* mutual-exclusion paragraph (proposal 0058).
- observability §5.5.7 — Typed LLM failure event framing.

**Cases:**

1. `failed_call_emits_only_llm_failed_event_never_completion` — Single LLM-calling node;
   mocked provider raises `provider_unavailable`. Asserts exactly one `LlmFailedEvent` AND
   exactly zero `LlmCompletionEvent`. Companion sense-check to fixture 069's mutual-exclusion
   assertion; dedicated standalone fixture so the rule has its own visible test.

**What passes:**

- Event-count of `LlmFailedEvent` on the failed call is exactly 1.
- Event-count of `LlmCompletionEvent` on the failed call is exactly 0.

**What fails:**

- The impl emits both events for the same call (e.g., emits `LlmCompletionEvent` with
  partial fields populated before transitioning to the failure path, then emits
  `LlmFailedEvent` for the same call). The spec mandates one-or-the-other, never both.
- The impl emits `LlmCompletionEvent` instead of `LlmFailedEvent` on a failed call (the
  success-only contract on `LlmCompletionEvent` is broken).
