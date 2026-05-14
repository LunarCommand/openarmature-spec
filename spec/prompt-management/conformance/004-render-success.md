# 004 — Render Success

Happy path for `PromptManager.render()`: fetch a prompt, render it with
a valid variable, assert the `PromptResult` carries propagated identity
fields and well-formed `messages`.

**Spec sections exercised:**

- §4 PromptResult shape — `name`, `label`, `version`, `template_hash`
  propagated from the source `Prompt`; `rendered_hash` computed from
  rendered messages; `messages` is a sequence of `Message` records
  per llm-provider §3; `variables` (the input) recorded on the result.
- §6 PromptManager.render() semantics — variables applied to template,
  result returned synchronously.

**What passes:**

- `PromptResult` has `name == "greeting"`, `label == "production"`,
  `version == "v1"`, `template_hash` matching source.
- `messages == [{role: "user", content: "Hello, Alice!"}]`.
- `rendered_hash` is a non-empty string in the same format as
  `template_hash` (SHA-256 hex prefix).
- `variables == {user: "Alice"}`.

**What fails:**

- Identity fields are missing or don't match the source `Prompt`.
- Messages don't reflect variable substitution.
- `rendered_hash` is empty or in a different format from `template_hash`.
