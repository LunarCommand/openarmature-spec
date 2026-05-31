# 021 — Chat-Prompt Empty Content Segment

Verifies §11's Chat-prompt empty-segment trigger: a text-template content segment whose
rendered text is the empty string raises `prompt_render_error`. There is NO silent-drop
behavior.

**Spec sections exercised:**

- §3.1 — content segment (text-template `content`).
- §11 — `prompt_render_error` empty-content-segment trigger.

**Cases:**

1. `empty_content_segment_raises` — chat_template with a literally-empty system content
   segment. Asserts `prompt_render_error` raised; error description mentions "empty".

**Harness extensions:** none new.

**What passes:**

- `prompt_render_error` raised; error carries the prompt's name / version / label and a
  description mentioning the empty segment.
- Render aborts; no partial PromptResult produced.

**What fails:**

- The system segment was silently dropped and render produced a PromptResult with only the
  user segment — violates the no-silent-drop rule. Callers needing optional segments must
  drive omission at the data layer (build a chat_template that excludes the segment) per
  the §11 paragraph.
- The empty segment was rendered to a `{role: "system", content: ""}` Message and passed
  through to the LLM — equally a violation; the spec mandates render-time rejection.
- Implementation treated "empty after stripping" differently from "literally empty" without
  documenting the choice; per §11 implementations document their convention, but at least
  one of the two MUST raise. The literal-empty case asserted here covers the unambiguous
  trigger.
