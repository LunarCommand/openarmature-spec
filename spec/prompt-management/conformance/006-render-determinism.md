# 006 — Render Determinism

Rendering the same `Prompt` with the same `variables` twice MUST
produce bytewise-identical `messages` and `rendered_hash`. Per §12's
determinism contract.

**Spec sections exercised:**

- §12 Determinism — "the same Prompt rendered with the same variables
  MUST produce a PromptResult whose messages and rendered_hash are
  bytewise identical across calls."
- §12 — implementations MUST NOT introduce wall-clock-derived,
  random, or process-state-derived content into render output.

**What passes:**

- Two renders with identical inputs produce equal `messages` and
  `rendered_hash`.
- Identity fields (name/version/label/template_hash) match.
- Timestamps (`rendered_at`) MAY differ — they reflect timing, not
  content.

**What fails:**

- `messages` differs across the two renders — would mean the implementation
  injected nondeterministic content (timestamps, random nonces, etc.).
- `rendered_hash` differs — same issue; the hash MUST reflect content
  deterministically.
