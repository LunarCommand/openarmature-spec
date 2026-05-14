# 005 — Render Undefined Variable

A template references a variable that is NOT in the `variables`
mapping passed to `render()`. Under §7's strict-by-default rule,
render MUST raise `prompt_render_error` rather than silently
substituting an empty string.

**Spec sections exercised:**

- §7 Variable injection — strict-undefined-by-default; undefined
  variables raise `prompt_render_error`.
- §10 — `prompt_render_error` error payload MUST expose name/version/
  label and a failure description.

**What passes:**

- `render()` raises `prompt_render_error`.
- The error payload carries `name`/`label`/`version` of the source
  prompt and a description that mentions the missing variable (`day`).

**What fails:**

- Render succeeds with `day` silently substituted as empty string —
  violates §7's strict-default rule.
- A different error category is raised.
- The error payload is missing identity fields or the failing variable.
