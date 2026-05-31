# 029 — Chat-Prompt Content-Blocks Empty Cases

Verifies two §11 Chat-prompt triggers that target content-blocks segments specifically:
an empty rendered text block within a content-blocks segment, and a content-blocks segment
whose block list is empty. Both raise `prompt_render_error`. Parallel to fixture 021
(empty text-template segment) but exercised inside the content-blocks shape.

**Spec sections exercised:**

- §3.1 — content-blocks template; text block template.
- §11 — `prompt_render_error` empty content-segment trigger (extended to per-block within
  content-blocks segments + empty block list).
- §8 — per-block strict-undefined (interacts with case 1 — the text-block template
  resolves a variable that's present but empty; this is the empty-after-substitution
  case, not the missing-variable case).

**Cases:**

1. `empty_rendered_text_block_in_content_blocks_raises` — user content-blocks segment
   with a text block (`text: "{{ description }}"`) and an image block. Render with
   `variables={"description": ""}`. Asserts `prompt_render_error` raised; text-block
   emptiness within a content-blocks segment is rejected the same way as a top-level
   empty text-template segment.
2. `empty_content_blocks_list_raises` — user content-blocks segment with `content: []`.
   Asserts `prompt_render_error` raised at render.

**Harness extensions:** none new.

**What passes:**

- Both cases raise `prompt_render_error`; errors carry name / version / label and
  descriptions mentioning the empty cause.
- Render aborts; no partial `PromptResult` produced in either case.

**What fails:**

- Case 1: the text block is silently dropped and only the image block survives in the
  rendered Message's content — implementations MUST NOT silently drop empty blocks; the
  per-block empty rule mirrors the segment-level empty rule.
- Case 1: the text block is rendered as a `{type: "text", text: ""}` block — equally a
  violation; the spec mandates render-time rejection of empty rendered text within
  content-blocks segments, same as for top-level text-template segments.
- Case 2: the segment is silently dropped, producing a `PromptResult` with messages of
  reduced length — implementations MUST reject the empty-block-list shape rather than
  producing an empty Message or skipping the segment.
- Case 2: the segment is rendered as a Message with `content: []` (empty block list) —
  violates the llm-provider §3.1 non-empty content-block sequence convention; the spec
  mandates rejecting at the prompt boundary.
