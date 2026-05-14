# 001 — Fetch Success

Smallest possible test: a backend with a known prompt returns the
expected `Prompt` record on `fetch(name, label)`. Establishes the
fundamental shape before testing nuances in 002-012.

**Spec sections exercised:**

- §3 Prompt shape — `name`, `label`, `version`, `template`,
  `template_hash` populated correctly.
- §5 PromptBackend protocol — `fetch(name, label="production")`
  returns a `Prompt` on success.

**What passes:**

- The returned `Prompt` carries name, label, version, template, and
  template_hash matching the backend's stored prompt.

**What fails:**

- Any field missing or incorrect on the returned `Prompt`.
- The fetch raises any error.
