# 058 — Call-level retry: non-transient propagates without retry

Verifies §7.1's non-transient propagation rule: "Exceptions classified as non-transient
propagate immediately on first occurrence (no retry)." Even when a `retry` parameter is
configured with `max_attempts > 1`, a non-transient exception (e.g., `provider_invalid_request`)
MUST propagate on attempt 0 without triggering a retry attempt.

**Spec sections exercised:**

- llm-provider §7.1 — Non-transient exceptions propagate immediately on first occurrence;
  the in-call retry loop only loops on transient categories.
- observability §5.5 — Single LLM span emits when call-level retry exits on attempt 0;
  `openarmature.llm.attempt_index = 0`.

**Cases:**

1. `non_transient_propagates_without_retry` — Mocked provider returns HTTP 400 (→
   `provider_invalid_request` per §7). `complete()` is called with `retry={max_attempts: 3,
   backoff: {deterministic 0}}`. Asserts:
   - The call raises `provider_invalid_request` on attempt 0 (does not iterate the retry
     loop).
   - Exactly ONE LLM provider span emits, carrying
     `openarmature.llm.attempt_index = 0` and the `provider_invalid_request` error category.
   - The retry loop's backoff sleep is NOT invoked (no retry attempted).

**What passes:**

- The call raises `provider_invalid_request` (the §7 non-transient category).
- Exactly one LLM span emits — the retry loop exited on the first non-transient occurrence.
- The single span carries `attempt_index = 0` and the error category.

**What fails:**

- The call raises after multiple attempts — the retry loop iterated despite the non-transient
  classification.
- More than one LLM span emits — the implementation retried on a non-transient.
- The error category is masked or transformed — the non-transient exception's category MUST
  propagate verbatim.
