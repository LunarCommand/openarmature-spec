# 073 — `LlmFailedEvent.error_type` vendor-specific + null companion

Verifies graph-engine §6's `LlmFailedEvent.error_type` field contract (per proposal 0058) —
OPTIONAL impl-level / vendor-specific error type or code. Spec text describes two
acceptable styles: a vendor error code and an upstream exception class name. Either style
satisfies the field contract; null is valid when no impl-side type is available.

**Spec sections exercised:**

- graph-engine §6 — `LlmFailedEvent.error_type` field (proposal 0058).
- llm-provider §7 — `provider_rate_limit`, `provider_unavailable` error categories.

**Cases:**

1. `error_type_populated_with_vendor_code_style` — Provider raises `provider_rate_limit`;
   the mocked vendor body carries an error code. Typed event carries the normative
   `error_category = "provider_rate_limit"` and a populated (non-empty) `error_type` — the
   fixture asserts it is populated, not the verbatim body value.
2. `error_type_populated_with_exception_class_name_style` — Provider raises
   `provider_rate_limit`; the mocked vendor body carries a class-name-style type. Like
   case 1, `error_type` is asserted populated (non-empty) regardless of how the impl sources
   it — the fixture does not pin the sourcing style (vendor code or exception class name both
   satisfy the contract).
3. `error_type_null_when_no_impl_side_type_available` — Provider raises `provider_unavailable`
   with no impl-side type detail. Typed event carries `error_category = "provider_unavailable"`
   and `error_type = null`. Companion sense-check that the OPTIONAL clause holds.

**What passes:**

- Cases 1 + 2: `error_type` is a non-empty string (asserted via the `<any-string>` matcher,
  not a verbatim value, so either sourcing style passes); `error_category` is the normative
  §7 category.
- Case 3: `error_type == null`; `error_category` is populated.

**What fails:**

- Cases 1/2: `error_type` is null or empty (the call raised with a surfaced type, so the
  field must be a non-empty string here), or `error_type` is collapsed to `error_category`'s
  value (the impl merged two distinct surfaces).
- Case 3: `error_type` is fabricated to a default like the empty string or a generic
  exception name (`Exception`) instead of null — the OPTIONAL clause means null is the
  correct value when no impl-side type exists.
- Any case: `error_category` is missing or non-§7 — the field is always-required per spec.
