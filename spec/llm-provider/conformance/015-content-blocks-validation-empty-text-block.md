# 015 — Content Blocks Empty Text Block Validation

A user message containing a `TextBlock` with `text == ""` (empty string)
in an otherwise non-empty content sequence MUST raise
`provider_invalid_request` at pre-send validation. Verifies §3.1.1's
"text MUST be a non-empty string" rule independently of the §3
sequence-must-be-non-empty rule.

**Spec sections exercised:**

- §3.1.1 Text block — `text` field MUST be a non-empty string.
- §7 — `provider_invalid_request` raised at pre-send validation.

**What passes:**

- The implementation raises `provider_invalid_request` before reaching
  the wire.

**What fails:**

- The empty-text block reaches the wire (would silently send a useless
  text entry).
- The sequence is allowed because it's non-empty overall (would mean the
  implementation only checks the §3 outer rule, not the §3.1.1 inner
  rule).
