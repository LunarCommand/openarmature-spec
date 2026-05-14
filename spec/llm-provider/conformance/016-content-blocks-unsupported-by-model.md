# 016 — Content Blocks Unsupported By Model

The bound model is configured as text-only (no image input capability).
A user message containing an image block MUST raise
`provider_unsupported_content_block` — either at pre-send validation
(static capability check) or post-receive (provider rejects the
request). Verifies the new §7 error category added by proposal 0015.

**Spec sections exercised:**

- §7 — `provider_unsupported_content_block` error category;
  non-transient; raised when "the bound model does not support a content
  block type used in the request."
- §3.1.2 — implicitly, image blocks are well-formed; the issue is
  capability mismatch, not structural shape.

**What passes:**

- The implementation raises `provider_unsupported_content_block`
  (either at pre-send validation or post-receive).

**What fails:**

- A different error category is raised (e.g., `provider_invalid_request`
  for a structurally valid block — would conflate shape and capability).
- The unsupported call is silently sent and produces a model-side error
  that doesn't get mapped to the new category.
