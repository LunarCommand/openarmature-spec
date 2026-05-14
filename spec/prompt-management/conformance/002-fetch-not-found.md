# 002 — Fetch Not Found

A backend with no prompt matching the requested `(name, label)` MUST
raise `prompt_not_found`. Verifies §5's contract that fetch raises
this category when no match exists.

**Spec sections exercised:**

- §5 PromptBackend — "fetch() MUST raise prompt_not_found when no
  prompt matches (name, label)."
- §10 — `prompt_not_found` is non-transient.

**What passes:**

- `fetch()` raises `prompt_not_found`.

**What fails:**

- A different error category is raised (e.g.,
  `prompt_store_unavailable` — but that's for infrastructure failure,
  not logical absence).
- The fetch returns successfully with a default/empty `Prompt` — would
  silently mask a missing prompt.
