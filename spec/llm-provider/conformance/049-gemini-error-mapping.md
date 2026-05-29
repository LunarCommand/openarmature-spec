# 049 — Gemini error mapping

Verifies §8.3.3 — HTTP status + Gemini `error.status` → §7 error category.

**Spec sections exercised:**

- §8.3.3 error mapping — 400 `INVALID_ARGUMENT` → `provider_invalid_request`; 401/403
  `PERMISSION_DENIED` / `UNAUTHENTICATED` → `provider_authentication`; 404 `NOT_FOUND` →
  `provider_invalid_model`; 429 `RESOURCE_EXHAUSTED` → `provider_rate_limit`; 500/503/504
  `INTERNAL` / `UNAVAILABLE` / `DEADLINE_EXCEEDED` → `provider_unavailable`.

**What passes:**

- Each HTTP status + `error.status` combination raises the mapped §7 category.

**What fails:**

- 429 surfaced as a generic error instead of `provider_rate_limit`.
- 404 `NOT_FOUND` surfaced as `provider_invalid_request` instead of `provider_invalid_model`.
- 503 `UNAVAILABLE` surfaced as a non-retryable category instead of `provider_unavailable`.
