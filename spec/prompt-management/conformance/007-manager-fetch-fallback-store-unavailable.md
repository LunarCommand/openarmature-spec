# 007 — Manager Fetch Fallback on Store Unavailable

A composite manager with two backends. The primary raises
`prompt_store_unavailable` (infrastructure failure). The secondary
has the prompt. The manager MUST fall back to the secondary per §8.

**Spec sections exercised:**

- §8 Composite backends and fallback — "If the backend raises
  prompt_store_unavailable, the manager tries the next backend."
- §6 PromptManager.fetch() — composite-fallback semantics.

**What passes:**

- The manager returns the secondary's prompt.
- The returned `Prompt.template_hash` is `"sha256:secondary"`
  (not primary's).

**What fails:**

- The manager raises `prompt_store_unavailable` despite the secondary
  being available — would mean fallback didn't fire.
- The manager returns the primary's prompt — impossible since primary
  was unavailable, but would indicate a stale-cache leak.
