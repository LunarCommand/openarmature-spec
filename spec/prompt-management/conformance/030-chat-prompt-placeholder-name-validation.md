# 030 — Chat-Prompt Placeholder Name Validation

Verifies §3.1's placeholder-name identifier-shape rule and the corresponding §11
`prompt_render_error` trigger. Placeholder names MUST match the regex
`[A-Za-z_][A-Za-z0-9_]*`; non-matching names raise at render time. Includes a positive
control to guard against an over-eager regex that rejects valid identifier-shaped names.

**Spec sections exercised:**

- §3.1 — placeholder-name regex constraint.
- §11 — `prompt_render_error` placeholder-name-regex-mismatch trigger.

**Cases:**

1. `placeholder_leading_digit_raises` — placeholder name `"1history"` starts with a
   digit; raises.
2. `placeholder_disallowed_char_raises` — placeholder name `"chat-history"` contains a
   hyphen; raises.
3. `placeholder_identifier_shaped_succeeds` — placeholder name `"_history_v2"` matches
   the regex; renders successfully with the injected list at the slot position. Positive
   control.

**Harness extensions:** none new.

**What passes:**

- Cases 1 + 2 raise `prompt_render_error` with the offending name in the description.
- Case 3 renders to the expected 3-Message sequence.

**What fails:**

- Cases 1 / 2 render successfully — implementation didn't enforce the regex constraint
  introduced by §3.1.
- Case 3 raises — implementation's regex is too restrictive (e.g., disallows leading
  underscores or disallows digits after the first character).
- The error description omits the offending name — callers can't identify which
  placeholder name violated.
