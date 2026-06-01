# 056 — Call-level retry: transient failure then success

Verifies §7.1's in-call retry loop: a `complete()` call with a `retry` parameter configured for
`max_attempts=2` retries a transient failure on attempt 0 and returns the successful response
on attempt 1. Two LLM spans emit (one per attempt) carrying
`openarmature.llm.attempt_index = 0` and `1` per observability §5.5.

**Spec sections exercised:**

- llm-provider §5 — `complete()` extended with optional `retry` kwarg.
- llm-provider §7.1 — Call-level retry loop: transient classification, max_attempts behavior,
  per-attempt span emission.
- observability §5.5 — `openarmature.llm.attempt_index` attribute on per-attempt spans;
  single-call-multi-span framing under retry.

**Cases:**

1. `call_level_retry_transient_then_success` — Mocked provider returns HTTP 503 (→
   `provider_unavailable` per §7) on attempt 0, then HTTP 200 with a successful chat completion
   on attempt 1. `complete()` is called with `retry={max_attempts: 2, backoff:
   {deterministic 0}}`. Asserts:
   - The call returns the successful response (does not raise).
   - Two LLM provider spans emit (parented under the same calling node span).
   - Attempt 0's span carries `openarmature.llm.attempt_index = 0` and a
     `provider_unavailable` error category.
   - Attempt 1's span carries `openarmature.llm.attempt_index = 1` and the successful response
     attributes (model, finish_reason, usage).

**What passes:**

- The call returns the successful response (transient → retry → success path works).
- Two per-attempt LLM spans emit with distinct `openarmature.llm.attempt_index` values.
- Attempt 0's span carries the error category; attempt 1's span carries the success
  attributes.

**What fails:**

- The call raises despite a successful attempt 1 — retry loop did not retry.
- Only one LLM span emits — the per-attempt span emission rule from §7.1 is not honored.
- The `openarmature.llm.attempt_index` attribute is missing or carries the wrong value on
  either span.
- Non-transient categories like `provider_invalid_request` retry (would mean the classifier
  widened beyond §6.1 defaults without caller config).
