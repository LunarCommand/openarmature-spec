# 039 — Anthropic error mapping

Verifies the §8.2.3 error-mapping table: HTTP status + Anthropic `error.type` → §7 category.

**Spec sections exercised:**

- §8.2.3 — the full HTTP-status / `error.type` → spec-category table.

**Cases:**

| Mock | Expected §7 category |
|---|---|
| 401 `authentication_error` | `provider_authentication` |
| 402 `billing_error` | `provider_authentication` |
| 403 `permission_error` | `provider_authentication` |
| 404 `not_found_error` (model) | `provider_invalid_model` |
| 413 `request_too_large` | `provider_invalid_request` |
| 429 `rate_limit_error` | `provider_rate_limit` |
| 500 `api_error` | `provider_unavailable` |
| 504 `timeout_error` | `provider_unavailable` |
| 529 `overloaded_error` | `provider_unavailable` |
| 400 content-block rejection | `provider_unsupported_content_block` |
| 400 `invalid_request_error` (other) | `provider_invalid_request` |

**What fails:**

- Any status mapped to the wrong category (e.g., 402 not grouped under auth; 504 not treated as
  unavailable; a content-block-rejection 400 mapped to generic `provider_invalid_request` instead
  of `provider_unsupported_content_block`).
