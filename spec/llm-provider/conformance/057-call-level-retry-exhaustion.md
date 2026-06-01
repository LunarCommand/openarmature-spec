# 057 — Call-level retry: exhaustion propagates final error

Verifies §7.1's exhaustion path. When `max_attempts` is exhausted, the final transient error
propagates per the normal `complete()` exception path. Both attempts' spans emit per the
single-call-multi-span framing.

**Spec sections exercised:**

- llm-provider §7.1 — Call-level retry exhaustion semantics.
- observability §5.5 — Per-attempt span emission under call-level retry.

**Cases:**

1. `call_level_retry_exhaustion_propagates_final_error` — Mocked provider returns HTTP 503 (→
   `provider_unavailable`) on both attempts. `complete()` is called with `retry={max_attempts:
   2, backoff: {deterministic 0}}`. Asserts:
   - The call raises `provider_unavailable` (the final attempt's error propagates per the
     normal exception path).
   - Two LLM provider spans emit with `openarmature.llm.attempt_index = 0` and `1`
     respectively; both carry `provider_unavailable` as their error category.

**What passes:**

- The call raises `provider_unavailable` after `max_attempts` are exhausted.
- Two per-attempt LLM spans emit; both carry the error category.
- The `openarmature.llm.attempt_index` attribute distinguishes the two spans.

**What fails:**

- The call returns a Response instead of raising — retry didn't propagate on exhaustion.
- Fewer than `max_attempts` spans emit — the per-attempt emission rule from §7.1 is not
  honored.
- The final attempt's error category does not propagate (e.g., a different category surfaces
  to the caller).
