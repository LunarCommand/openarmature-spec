# 014 — Content Blocks Empty Sequence Validation

A user message with `content: []` (empty content-block sequence) MUST
be rejected at pre-send validation with `provider_invalid_request`.
Verifies §3 per-role constraint: the content-block sequence MUST be
non-empty.

**Spec sections exercised:**

- §3 Message shape — user-role per-role constraint: content-block
  sequence MUST be non-empty.
- §7 — `provider_invalid_request` raised at pre-send validation.
- §3.1.4 — explicit statement: "A content-block sequence MUST NOT be
  empty."

**What passes:**

- The implementation raises `provider_invalid_request` before any wire
  call happens (the mock provider is never invoked).

**What fails:**

- The empty sequence reaches the wire — would mean pre-send validation
  isn't enforcing the non-empty constraint.
- A different error category is raised (e.g., `provider_unsupported_content_block`)
  — would mean the implementation conflated structural shape errors with
  capability errors.
