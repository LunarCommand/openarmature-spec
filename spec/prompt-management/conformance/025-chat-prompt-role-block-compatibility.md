# 025 — Chat-Prompt Role-Block Compatibility

Verifies §11's Chat-prompt role-block-compatibility trigger: a content-blocks segment
containing any image block MUST have `role: "user"` per llm-provider §3.1.2. A non-user
role with an image-block-containing template raises `prompt_render_error` at render time.

**Spec sections exercised:**

- §3.1 — content-blocks template; image blocks user-only per llm-provider §3.1.2 cross-
  reference.
- §11 — `prompt_render_error` role-block-compatibility trigger; render-time enforcement
  point.

**Cases:**

1. `image_block_in_non_user_segment_raises` — chat_template with a `role: "system"`
   content-blocks segment containing an image block. Asserts `prompt_render_error` raised
   at render; error description mentions "image".

**Harness extensions:** none new.

**What passes:**

- `prompt_render_error` raised at render time.
- Error carries name / version / label and a description mentioning the violating block
  type (image) and / or the segment's role.
- No partial `PromptResult` produced (the render aborts before walking the second user
  segment).

**What fails:**

- The render produced a Message with `role: "system"` carrying the image block — violates
  llm-provider §3.1.2 "image blocks are user-only" via the §11 cross-spec enforcement.
  The spec mandates rejecting at the prompt boundary so the violation surfaces here, not
  downstream at `Provider.complete()`.
- The image block was silently demoted (role re-tagged to `"user"` by the renderer) —
  implementations MUST NOT mutate the segment's authored role; the spec mandates error.
- The image block was silently dropped, producing a system Message with only the text
  block — equally a violation; the spec mandates rejecting the chat_template, not
  partial-rendering it.
- The error was raised but only after the LLM call layer rejected it — per §11 the
  spec-normative point of enforcement is render, the earliest point at which both the
  segment's role and its block list are known.
