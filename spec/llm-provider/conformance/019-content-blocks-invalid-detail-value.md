# 019 — Content Blocks Invalid Detail Value

An image block with a `detail` value outside the §3.1.2 enum
(`"auto"`, `"low"`, `"high"`) MUST be rejected at pre-send validation
with `provider_invalid_request`. Verifies the structural enum
enforcement; complements fixture 012's happy-path coverage of the
detail hint.

**Spec sections exercised:**

- §3.1.2 Image block — `detail` enum: one of `"auto"`, `"low"`, `"high"`.
- §7 — `provider_invalid_request` raised at pre-send validation when
  per-block constraints are violated.

**What passes:**

- The implementation raises `provider_invalid_request` before reaching
  the wire (the unsupported hint is rejected at the spec boundary).

**What fails:**

- The unsupported value is passed through to the wire — would mean the
  implementation isn't enforcing the §3.1.2 enum.
- A different error category is raised (e.g., the implementation invents
  a "bad enum" category instead of using `provider_invalid_request`).
