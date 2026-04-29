# 006 — Usage Accounting

Verifies that `Response.usage` is populated correctly in both directions: when the provider
supplies a usage record, the integers flow through; when usage is absent, all three subfields
are explicitly `null`.

**Spec sections exercised:**

- §6 Response.usage — `prompt_tokens`, `completion_tokens`, `total_tokens` as non-negative
  integer or null. If usage is absent on the wire, all three MUST be null.

**Cases:**

1. `usage_populated` — provider response carries `usage: {prompt_tokens: 100,
   completion_tokens: 50, total_tokens: 150}`. The spec `Response.usage` carries the same
   integers.
2. `usage_absent` — provider response has no `usage` field. The spec `Response.usage` has
   all three subfields explicitly `null`.

**What passes:**

- Case 1: each subfield is the exact integer from the mock body.
- Case 2: each subfield is `null` (not `0`, not omitted, not raised — explicit null).

**What fails:**

- The implementation defaults missing usage subfields to `0` instead of `null` (this would
  silently corrupt cost-tracking dashboards).
- The implementation omits the `usage` field entirely from `Response` rather than presenting
  the explicit-null record.
- The implementation copies a non-integer or negative value (the mock provides valid integers,
  so any divergence indicates a transformation bug).
