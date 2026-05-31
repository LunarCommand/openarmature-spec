# 017 — Chat-Prompt Per-Segment Render (Static)

Verifies §3.1 Chat-prompt variant and §6.render chat render contract for the simplest static
case: a two-segment `chat_template` (system + user, each text-template `content` with one
variable) renders to a two-Message `PromptResult` with per-segment substitution applied
independently.

**Spec sections exercised:**

- §3.1 — Chat-prompt variant; `chat_template: list[ChatSegment]`; content segment with
  text-template `content`.
- §6.render — Chat-prompt render contract; one Message per content segment, role propagated,
  variable substitution per segment.
- §8 — per-segment strict-undefined (positive case — all referenced variables supplied).

**Cases:**

1. `chat_per_segment_render` — two-segment chat_template with variables in each segment;
   render produces messages of length 2 with correct roles and substituted content.

**Harness extensions:**

- `chat_template: [<ChatSegment>, ...]` on a backend's prompt definition — declares the
  Chat-prompt variant in place of `template`.
- ChatSegment as `{role, content}` for text-template content segments.

**What passes:**

- `PromptResult.messages` has length 2.
- `messages[0]` is `{role: "system", content: "You classify support requests."}` (system
  segment with `topic` substituted).
- `messages[1]` is `{role: "user", content: "Classify: my order is late"}` (user segment
  with `input` substituted).
- Per-segment substitution: `topic` resolved against the system segment's references,
  `input` resolved against the user segment's references; no leakage.

**What fails:**

- `messages` has length 1 with both rendered texts concatenated — implementation flattened
  the chat_template into a single Message instead of producing per-segment messages.
- Either Message carries the wrong role — implementation didn't propagate segment role.
- Variable substitution happened against a merged variable scope in a way that masked an
  undefined variable in one segment — see fixture 020 for the explicit per-segment
  strict-undefined case.
- The Text-prompt path was inadvertently routed (implementation didn't discriminate the
  variant) — `chat_template` was treated as a stringifiable template producing one Message.
