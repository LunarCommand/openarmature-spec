# 073 — `LlmFailedEvent.error_type` vendor-specific + null companion

Verifies graph-engine §6's `LlmFailedEvent.error_type` field contract (per proposal 0058) —
OPTIONAL impl-level / vendor-specific error type or code. Spec text describes two
acceptable styles: a vendor error code and an upstream exception class name. Either style
satisfies the field contract; null is valid when no impl-side type is available.

**Spec sections exercised:**

- graph-engine §6 — `LlmFailedEvent.error_type` field (proposal 0058).
- llm-provider §7 — `provider_rate_limit`, `provider_unavailable` error categories.

**Cases:**

1. `error_type_populated_with_vendor_code_style` — Provider surfaces `error_type` as a
   vendor error code (`"rate_limit_exceeded"`). Typed event carries the normative
   `error_category = "provider_rate_limit"` AND the vendor-specific `error_type`.
2. `error_type_populated_with_exception_class_name_style` — Provider surfaces `error_type`
   as an upstream exception class name (`"RateLimitError"`). Same `error_category` as
   case 1 (both raise `provider_rate_limit`); demonstrates the two acceptable `error_type`
   styles the spec text permits.
3. `error_type_null_when_no_impl_side_type_available` — Provider raises `provider_unavailable`
   with no impl-side type detail. Typed event carries `error_category = "provider_unavailable"`
   and `error_type = null`. Companion sense-check that the OPTIONAL clause holds.

**What passes:**

- Cases 1 + 2: `error_type` carries the vendor's value verbatim (code-style or
  class-name style); `error_category` is the normative §7 category.
- Case 3: `error_type == null`; `error_category` is populated.

**What fails:**

- Cases 1/2: `error_type` is collapsed to `error_category`'s value (the impl merged the
  two fields) — the spec carves them as distinct surfaces.
- Case 3: `error_type` is fabricated to a default like the empty string or a generic
  exception name (`Exception`) instead of null — the OPTIONAL clause means null is the
  correct value when no impl-side type exists.
- Any case: `error_category` is missing or non-§7 — the field is always-required per spec.
