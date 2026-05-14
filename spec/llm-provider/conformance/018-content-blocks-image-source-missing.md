# 018 — Content Blocks Image Source Missing

An image block constructed without a `source` field MUST be rejected at
pre-send validation with `provider_invalid_request`. Verifies the
§3.1.2 "`source` required" rule and the §3.1.3 XOR-source rule
structurally — an image block without any source variant is malformed
regardless of provider capability.

**Spec sections exercised:**

- §3.1.2 Image block — `source` field is required.
- §3.1.3 Image source — "A single image block carries exactly one source
  — `url` XOR `inline`."
- §7 — `provider_invalid_request` raised at pre-send validation when
  per-role / per-block constraints are violated.

**What passes:**

- The implementation raises `provider_invalid_request` before reaching
  the wire (the mock provider is never invoked).

**What fails:**

- The malformed image block reaches the wire — would mean pre-send
  validation isn't enforcing the `source` requirement.
- A different error category is raised (e.g.,
  `provider_unsupported_content_block`) — would conflate structural
  malformation with capability mismatch (the block is malformed
  regardless of what the provider supports).
