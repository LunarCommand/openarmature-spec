# 018 — Chat-Prompt Placeholder List-Injection (Non-Empty)

Verifies §3.1 placeholder segments and §6.render placeholder substitution rule for the
non-empty injection case. A chat_template with a placeholder segment between a system and a
final user segment expands the caller-supplied `list[Message]` at the slot position,
in-order, as standalone Messages (no merging with surrounding segments).

**Spec sections exercised:**

- §3.1 — placeholder segment `{placeholder: str}`.
- §6.render — `placeholders` parameter; placeholder segment substitution; injected Messages
  appear standalone at the slot position.

**Cases:**

1. `placeholder_injection_non_empty` — chat_template [system, placeholder("history"), user];
   render with placeholders={"history": [user-prior, assistant-prior]}; asserts the
   resulting messages sequence is [system, prior-user, prior-assistant, final-user] in
   order.

**Harness extensions:**

- `placeholders: {<name>: [<Message>, ...]}` on a render call — the optional
  `placeholders` parameter from §6.render.

**What passes:**

- `PromptResult.messages` has length 4 in the exact order [system, prior-user,
  prior-assistant, final-user].
- The injected pair appears standalone (each as its own Message) at the slot position; no
  merging with the surrounding system or final-user segments.
- The final user segment's variable `user_turn` is substituted correctly.

**What fails:**

- The injected Messages were merged with adjacent content segments (e.g., the prior-user
  message's content prepended to the final user message's content) — violates the
  "standalone" rule from §6.render.
- The placeholder segment was substituted before variable rendering, causing variable
  references in the injected Messages to be re-rendered against `variables` —
  implementations MUST NOT re-render injected Messages; they pass through as-is.
- The injected list was reordered (sorted, deduped, etc.) — implementations MUST preserve
  the caller-supplied order.
- The placeholder name lookup matched against a stringified path (e.g., `"history.0"`
  instead of `"history"`) — placeholder names are flat top-level keys per §3.1.
