# 020 — Content Blocks Inline Image Missing media_type

An image block with `source: inline` but no `media_type` field MUST be
rejected at pre-send validation with `provider_invalid_request`.
Verifies the §3.1.2 conditional-required rule: `media_type` is
required when `source` is `inline`. Without this rule enforced,
implementations could construct invalid data URIs of the form
`data:;base64,...` (no media type) that providers will reject anyway.

**Spec sections exercised:**

- §3.1.2 Image block — `media_type` is conditional, required when
  `source` is `inline`.
- §3.1.3 Image source — the `inline` source variant.
- §8.1.1 Content-block wire mapping — the inline-image row reads
  `media_type` from the ImageBlock to construct the data URI per
  RFC 2397; the wire mapping requires media_type to exist.
- §7 — `provider_invalid_request` raised at pre-send validation when
  per-block constraints are violated.

**What passes:**

- The implementation raises `provider_invalid_request` before reaching
  the wire (no data URI is ever constructed).

**What fails:**

- A malformed `data:;base64,...` URI reaches the wire — would mean the
  implementation didn't enforce media_type's conditional-required
  status.
- A different error category is raised (e.g.,
  `provider_unsupported_content_block`) — would conflate structural
  malformation with capability mismatch.
- The implementation silently substitutes a default media_type (e.g.,
  `image/png`) — would mean it's covering up the user's omission
  instead of surfacing it.
