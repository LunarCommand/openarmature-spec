# 001 — Basic send-and-reply cycle (§5 + §6 + §7)

The chat harness's `send()` callable accepts a user `ChatMessage`, runs the
graph through one turn, and returns a `ChatTurnOutcome.completed` carrying
the new assistant reply on the `.replies` list. This is the canonical
single-turn cycle exercising the inbound + outbound wiring.

This fixture also carries the chat suite's **per-directory contract**
documentation in its YAML header comment per conformance-adapter §3.2 — the
chat-specific assertion vocabulary (`chat_turns:`, `expected.outcome:`,
`expected.replies:`, `expected.reply:`, `expected.pending_message:`,
`expected.signal_descriptor:`) layers on top of the base directive set.

**Spec sections exercised:**

- harness-chat §5 — `send()` callable + `ChatTurnOutcome` shape
- harness-chat §6 — inbound message → session → invoke wiring
- harness-chat §7 — outbound assistant message → response wiring
- harness-chat §4 — conversation-history `messages` field

**What passes:**

- `send()` returns a `ChatTurnOutcome.completed`.
- `.replies` contains exactly one message (the new assistant reply).
- `.replies[0]` has `role: assistant` and `content: "Hi there"`.
- Final session state's `messages` field has 2 entries (the user message
  appended at inbound + the assistant reply appended by the graph).

**What fails:**

- `send()` returns an `errored` or `suspended` outcome — would mean the
  basic-reply path is broken.
- `.replies` is empty or has the wrong message — would mean §7's tail
  extraction is broken.
- `.replies` contains the user message — would mean §7's "new messages
  only" rule isn't being honored (pre-invoke history leaking into the
  reply tail).
