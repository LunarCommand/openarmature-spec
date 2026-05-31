# 027 — Chat-Prompt Empty Rendered Messages

Verifies §11's Chat-prompt empty-rendered-messages trigger and the §4 non-empty
`PromptResult.messages` invariant: a Chat-prompt render that produces zero rendered
Messages (e.g., a chat_template of only placeholder segments that all inject empty lists)
MUST raise `prompt_render_error`. The per-placeholder empty-list-valid rule (fixture 019)
remains intact for partial cases — only the global-empty result is rejected.

**Spec sections exercised:**

- §3.1 — placeholder segment.
- §4 — `PromptResult.messages` non-empty invariant.
- §6.render — final-messages-non-empty rule.
- §11 — `prompt_render_error` empty-rendered-messages trigger.

**Cases:**

1. `single_empty_placeholder_raises` — chat_template `[{placeholder: "history"}]` rendered
   with `placeholders={"history": []}`. Zero rendered Messages; asserts
   `prompt_render_error` raised; error description mentions "empty".
2. `multiple_empty_placeholders_raise` — chat_template with two placeholder segments
   (`[{placeholder: "examples"}, {placeholder: "history"}]`), both injected with empty
   lists. Combined output is still zero Messages; the §11 global rule fires regardless of
   per-slot cardinality.

**Harness extensions:** none new.

**What passes:**

- `prompt_render_error` raised; error carries name / version / label and a description
  mentioning the empty rendered result.
- Render aborts; no `PromptResult` produced.

**What fails:**

- An empty `PromptResult` (with `messages = []`) is returned to the caller — violates §4's
  non-empty invariant and §11's empty-rendered-messages trigger. The §4 contract is
  normative; constructing a PromptResult that violates it is a spec violation, not a
  best-effort partial result.
- A synthetic placeholder Message is fabricated to keep `messages` non-empty (e.g., `{role:
  "user", content: "<empty>"}`) — implementations MUST NOT fabricate content; the spec
  mandates error.
- Render succeeds because the per-placeholder empty-list rule (fixture 019) was applied
  globally — fixture 019's rule is per-placeholder ("empty injection contributes zero
  messages"); the §6.render final-messages-non-empty paragraph adds the global non-empty
  constraint that this fixture exercises.
