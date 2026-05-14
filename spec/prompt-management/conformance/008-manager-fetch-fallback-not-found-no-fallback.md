# 008 — Manager Fetch No Fallback on Not Found

Composite manager with two backends. The primary raises
`prompt_not_found` (logical absence). The secondary HAS the prompt.
The manager MUST raise `prompt_not_found` — the secondary's copy MUST
NOT silently surface. Per §8's "not-found stops the chain" rule.

The intent: an operator who deletes a prompt from a vendor backend
(retiring it) MUST see the deletion reflected in the manager's
fetch result — not silently overridden by a stale local fallback.

**Spec sections exercised:**

- §8 Composite backends and fallback — "If the backend raises
  prompt_not_found, the fallback chain stops."
- §8 rationale — distinguishes logical absence from infrastructure
  failure; the chain falls back only on the latter.

**What passes:**

- The manager raises `prompt_not_found`.
- The secondary backend's `fetch()` is NEVER invoked.

**What fails:**

- The manager returns the secondary's prompt — would silently mask
  the primary's deliberate absence (production bug magnet).
- The manager raises a different error category.
- The secondary backend's fetch is invoked even once — would mean the
  not-found-stops-chain rule was violated.
