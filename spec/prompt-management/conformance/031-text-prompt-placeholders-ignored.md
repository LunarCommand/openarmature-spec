# 031 — Text-Prompt Ignores Placeholders

Verifies §6.render's "placeholders MUST be ignored when rendering a Text prompt" rule. A
caller passing a non-empty `placeholders` mapping alongside a Text-prompt renders
identically to omitting `placeholders` entirely — no error, no synthesized injection.
This enables generic wrappers around `render()` to pass `placeholders` unconditionally
without per-variant discrimination.

**Spec sections exercised:**

- §6.render — Text-prompt render contract; `placeholders` MUST-be-ignored rule.

**Cases:**

1. `text_prompt_ignores_placeholders` — Text-prompt rendered with a non-empty
   `placeholders` mapping (containing entries that would inject Messages if this were a
   Chat-prompt). Asserts the result is a single-user-Message PromptResult identical to
   the no-placeholders render path.

**Harness extensions:** none new.

**What passes:**

- `PromptResult.messages` has length 1: `[{role: "user", content: "Hello, Alice!"}]`.
- No error raised despite the non-empty `placeholders` mapping.
- The result is bytewise identical to rendering with `placeholders=None`.

**What fails:**

- Render raises an error — implementation conflated "placeholders ignored" with
  "placeholders rejected on Text-prompt." The §6.render text pins MUST-be-ignored.
- The placeholders' injected Messages appear in the rendered output — implementation
  applied Chat-prompt render rules to the Text-prompt path.
- The Text-prompt render emitted a warning that surfaced as a test failure — warnings
  are out of scope for the spec contract but MUST NOT block the render or change the
  result.
