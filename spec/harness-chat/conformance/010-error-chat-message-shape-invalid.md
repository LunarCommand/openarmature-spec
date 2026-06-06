# 010 — `chat_message_shape_invalid` error (§10.4)

The caller sends a malformed `ChatMessage` — a `tool`-role message without
the required `tool_call_id` field per llm-provider §3. The chat harness
catches this at the `send()` API boundary (per §3.1 validation timing) and
surfaces `chat_message_shape_invalid` as a user-correctable error (routed
through harness §7.3 per §10.3 + §10.4).

The fixture pins both the validation-timing rule (§3.1: validation runs
BEFORE any session load) and the routing rule (§10.4: the new chat-specific
category lives in the chat-harness layer and maps to §7.3 on surfacing —
no change to harness §10's abstract error set).

**Spec sections exercised:**

- harness-chat §3.1 — message validation timing
- harness-chat §10.4 — new `chat_message_shape_invalid` error category
- harness-chat §10.3 — user-correctable error reply mapping
- harness §7.3 — user-correctable error bucket
- llm-provider §3 — per-role required-field rules

**What passes:**

- `send()` returns `ChatTurnOutcome.errored` without invoking the graph
  body.
- `.error_category` is `"user_correctable"`.
- `.error_diagnostic` is `"chat_message_shape_invalid"`.
- `.reply` is a `role: system` message including the user-correctable
  "adjust your message" framing.
- No session-store load is attempted (validation runs at the API boundary
  BEFORE session load).

**What fails:**

- The graph body executes despite the malformed input — would mean §3.1's
  pre-session-load validation timing is broken.
- `.error_category` is `session_terminating` — would mean the
  user-correctable routing for chat-specific errors is broken.
- The error surfaces as a different category (e.g., raw
  `chat_message_shape_invalid` exposed as `.error_category` directly,
  bypassing harness §7.3) — would mean the new category isn't routing
  through the abstract harness error surface.
