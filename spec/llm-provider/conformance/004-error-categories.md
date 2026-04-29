# 004 — Error Categories

Table-style fixture: each case is a mock provider failure that maps to a specific §7 error
category per the §8.3 OpenAI wire mapping. Verifies that the implementation classifies provider
errors correctly and that callers can branch on category.

The fixture format is the table-style shape: each `cases:` entry has its own `mock_provider`,
`call`, and `expected.raises` block.

**Spec sections exercised:**

- §7 Error semantics — all six canonical categories from the §7 list, plus
  `provider_model_not_loaded`.
- §8.3 OpenAI error mapping — HTTP status codes and bodies map to spec categories.
- §7 Retry classification — implicitly verified by the categorization (downstream retry middleware
  consumes these categories per their transient/non-transient labels).

**Cases:**

1. `authentication_401` — HTTP 401 → `provider_authentication`.
2. `invalid_model_404` — HTTP 404 with model-not-found body → `provider_invalid_model`.
3. `model_not_loaded_503` — HTTP 503 with model-loading body → `provider_model_not_loaded`. The
   distinction from `provider_invalid_model` is operationally important: warmup-polling callers
   retry on `provider_model_not_loaded` but not on `provider_invalid_model`.
4. `rate_limit_429` — HTTP 429 → `provider_rate_limit`. Implementations SHOULD also expose
   `retry_after` from the `Retry-After` header (the YAML's `retry_after_seconds` field is
   asserted when the implementation supports it; otherwise it's informational).
5. `server_error_500` — HTTP 500 → `provider_unavailable`.
6. `malformed_response_200` — HTTP 200 but body can't be parsed (missing `choices`) →
   `provider_invalid_response`.
7. `connection_failure` — network failure (connection refused / DNS / timeout) →
   `provider_unavailable`. The harness's mock supports a `connection_failure: true` flag.

**What passes:**

- Each case raises an error whose `category` matches the expected value.
- For `rate_limit_429`, the `retry_after` accessor (when implemented) returns 30 seconds.

**What fails:**

- Any case raises a different category (e.g., 503 mapped to `provider_unavailable` rather than
  `provider_model_not_loaded`).
- Network failures raise without a category (e.g., a raw `ConnectionRefusedError` without the
  `provider_unavailable` wrapper).
- The 200-with-malformed-body case raises something other than `provider_invalid_response`.
