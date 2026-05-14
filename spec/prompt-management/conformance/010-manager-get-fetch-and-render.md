# 010 — Manager Get Convenience Equivalence

`manager.get(name, label, variables)` MUST be equivalent to
`render(await fetch(name, label), variables)` per §6. The fixture
exercises both paths and asserts the resulting `PromptResult` records
match on all content fields (identity, hashes, messages, variables).

**Spec sections exercised:**

- §6 PromptManager.get() — "Equivalent to render(await fetch(name,
  label), variables)."
- §6 fetch + render separability — `get()` is a convenience over the
  fetch+render composition; semantics MUST be identical.

**What passes:**

- The two results match on `name`, `version`, `label`, `template_hash`,
  `rendered_hash`, `messages`, and `variables`.
- `rendered_at` MAY differ (timing-only).

**What fails:**

- Any content field differs between the explicit fetch+render and the
  `get()` convenience — would mean `get()` isn't actually equivalent.
- `get()` raises while the explicit path succeeds (or vice versa).
