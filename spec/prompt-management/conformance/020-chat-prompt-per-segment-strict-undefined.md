# 020 — Chat-Prompt Per-Segment Strict-Undefined

Verifies §8 strict-undefined applies INDEPENDENTLY per segment for Chat prompts: a variable
referenced in one segment but absent from `variables` raises `prompt_render_error` for that
segment and aborts the render — even when other segments would have rendered successfully.

**Spec sections exercised:**

- §8 — strict-undefined (per-segment scope clarification for Chat prompts).
- §11 — `prompt_render_error` undefined-variable trigger.
- §6.render — render aborts before producing a partial PromptResult.

**Cases:**

1. `per_segment_strict_undefined_raises` — chat_template with two content segments, each
   referencing a different variable; only one variable supplied at render. Asserts
   `prompt_render_error` raised, error carries name / version / label, and the description
   mentions the missing variable name (`missing_input`).

**Harness extensions:**

- `expected.raises.carries.description_mentions: "<substring>"` — same convention as
  fixture 005 (the Text-prompt undefined-variable case).

**What passes:**

- `prompt_render_error` raised with category `prompt_render_error`.
- Error carries the prompt's `name`, `version`, `label`.
- Error description mentions `missing_input` (the absent variable name).
- No `PromptResult` produced (no partial result returned alongside the error).

**What fails:**

- Render produces a partial `PromptResult` containing only the system segment's rendered
  Message and silently drops the user segment — implementation didn't enforce the §6.render
  abort rule. The render MUST raise and produce no result.
- Variable scope was treated as global across segments rather than per-segment — e.g., the
  implementation merged all referenced variables across segments and only raised when no
  segment could resolve `missing_input` (this happens to produce the same error here but
  misses the per-segment scope intent; fixture 020 doesn't distinguish that from the
  correct case, but the spec text is clear).
- The user segment's missing variable was substituted with an empty string or `null` —
  violates §8 strict-by-default.
