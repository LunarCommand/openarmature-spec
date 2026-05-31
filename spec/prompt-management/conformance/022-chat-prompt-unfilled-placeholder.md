# 022 — Chat-Prompt Unfilled Placeholder

Verifies §11's Chat-prompt unfilled-placeholder trigger: a `{placeholder: <name>}` segment
whose `<name>` is absent from `placeholders` raises `prompt_render_error`. Distinct from
the `placeholders[<name>] = []` valid case covered by fixture 019.

**Spec sections exercised:**

- §3.1 — placeholder segment.
- §11 — `prompt_render_error` unfilled-placeholder trigger; distinction between absent
  (error) and present-with-empty-value (valid).

**Cases:**

1. `unfilled_placeholder_raises_absent` — render with no `placeholders` parameter at all.
   Asserts `prompt_render_error` raised with description mentioning the missing slot name.
2. `unfilled_placeholder_raises_missing_key` — render with a `placeholders` mapping that
   does NOT contain the slot's name (e.g., `{"other": []}`). Same error; the missing-key
   and absent-mapping cases are equivalent.

**Harness extensions:** none new.

**What passes:**

- Both cases raise `prompt_render_error`; the error description mentions the missing slot
  name (`examples`).
- Both errors carry name / version / label.

**What fails:**

- The placeholder slot was silently elided and render produced `[system, final-user]`
  (length 2) — implementation treated "unfilled" as "no contribution," conflating with
  the empty-list case. The §11 distinction is normative: absent → error; empty list →
  valid (fixture 019).
- The placeholder was substituted with a synthetic placeholder Message (e.g., `{role:
  "user", content: "<no examples provided>"}`) — implementations MUST NOT fabricate
  injection content; the spec mandates error.
- The error description omits the slot name, leaving the caller unable to identify which
  placeholder was unfilled.
