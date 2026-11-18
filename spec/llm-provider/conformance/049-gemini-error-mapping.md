# 049 — Gemini error mapping

Verifies §8.3.3 — HTTP status + Gemini `error.status` → §7 error category.

**Spec sections exercised:**

- §8.3.3 error mapping — 400 `INVALID_ARGUMENT` → `provider_invalid_request`; 401/403
  `PERMISSION_DENIED` / `UNAUTHENTICATED` → `provider_authentication`; 404 `NOT_FOUND` →
  `provider_invalid_model`; 429 `RESOURCE_EXHAUSTED` → `provider_rate_limit`; 500/503/504
  `INTERNAL` / `UNAVAILABLE` / `DEADLINE_EXCEEDED` → `provider_unavailable`.
- §8.3.3 *Precedence*: a 400 whose message says the model rejected a content part (`content_part_rejected_400`,
  an unsupported image MIME type) maps to `provider_unsupported_content_block`, ahead of the
  `INVALID_ARGUMENT` row. The plain 400 in `invalid_argument_400` still maps to `provider_invalid_request`.

**What passes:**

- Each HTTP status + `error.status` combination raises the mapped §7 category.

**What fails:**

- The content-part rejection surfaced as `provider_invalid_request` because its status is `INVALID_ARGUMENT`.
- 429 surfaced as a generic error instead of `provider_rate_limit`.
- 404 `NOT_FOUND` surfaced as `provider_invalid_request` instead of `provider_invalid_model`.
- 503 `UNAVAILABLE` surfaced as a non-retryable category instead of `provider_unavailable`.
