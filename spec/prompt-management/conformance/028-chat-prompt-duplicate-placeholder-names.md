# 028 — Chat-Prompt Duplicate Placeholder Names

Verifies §3.1's "placeholder names MUST be unique within a single chat_template" rule and
§11's duplicate-placeholder-name `prompt_render_error` trigger. A chat_template with two
`{placeholder: <same name>}` segments raises at render time regardless of what
`placeholders` contains.

**Spec sections exercised:**

- §3.1 — placeholder segment uniqueness constraint.
- §11 — `prompt_render_error` duplicate-placeholder trigger; render-time enforcement.

**Cases:**

1. `duplicate_placeholder_name_raises` — chat_template with two `{placeholder: examples}`
   segments. Asserts `prompt_render_error` raised at render; supplying the placeholder
   mapping does NOT bypass the rule (the violation is intrinsic to the chat_template, not
   conditional on the caller's `placeholders` argument).

**Harness extensions:** none new.

**What passes:**

- `prompt_render_error` raised at render time with category `prompt_render_error`.
- Error carries name / version / label and a description mentioning the duplicated
  placeholder name (`examples`).
- Render aborts; no partial `PromptResult` produced.

**What fails:**

- Render proceeds with both placeholder segments substituted (the same injected list at
  both positions) — implementations MUST NOT silently allow duplicates; the spec mandates
  rejection.
- Only the first occurrence of the duplicated placeholder is substituted and the second is
  silently dropped — same violation, different shape.
- The error is raised but only after one of the substitutions succeeded, leaving a partial
  `PromptResult` — render MUST abort cleanly with no partial state per §6.render.
- The error description omits the duplicated name, leaving the caller unable to identify
  which placeholder was duplicated.
