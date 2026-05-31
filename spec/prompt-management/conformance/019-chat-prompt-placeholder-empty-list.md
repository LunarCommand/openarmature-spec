# 019 — Chat-Prompt Placeholder List-Injection (Empty-List Valid)

Verifies that `placeholders[<name>] = []` (present-with-empty-value) contributes zero
messages and is NOT a render error. This is the canonical first-turn / no-prior-messages
case for a chat-history layer; it MUST be handled natively by empty-list injection rather
than by working around the §11 empty-segment or unfilled-placeholder rules.

**Spec sections exercised:**

- §3.1 — placeholder segment.
- §6.render — empty-list injection rule ("An injected `list[Message]` MAY be empty; an
  empty list contributes zero messages to the output and is NOT an error.").
- §11 — distinction between `placeholders[<name>] = []` (valid, zero messages) and
  `<name>` absent from `placeholders` (error; covered by fixture 022).

**Cases:**

1. `placeholder_injection_empty_list_valid` — same chat_template as fixture 018, rendered
   with `placeholders={"history": []}`. Asserts resulting messages is `[system,
   final-user]` (length 2) with no error.

**Harness extensions:**

- `placeholders: {<name>: []}` on a render call — empty list is the empty-injection case.

**What passes:**

- `PromptResult.messages` has length 2: `[system, final-user]`.
- No render error raised; the placeholder slot's empty injection contributes zero messages
  but the render proceeds successfully.
- The final user segment's variable substitution applies normally.

**What fails:**

- `prompt_render_error` raised for "unfilled placeholder" — implementation conflated
  "present with empty value" with "absent" and incorrectly treated `placeholders[<name>] =
  []` as an unfilled slot. The §11 distinction is normative.
- `prompt_render_error` raised for "empty-content segment" applied to the placeholder
  segment — implementations MUST NOT extend the empty-segment rule to placeholder slots;
  empty placeholder injection is the chat-history first-turn case and is valid.
- The placeholder slot was synthesized into a placeholder Message (e.g., a "no history"
  string) — implementations MUST contribute zero messages from an empty injection, not
  substitute a synthetic message.
