# 002 — Multi-turn conversation (§4 + §6)

Sequential `send()` calls under the same `session_id` accumulate history via
the `append` reducer. Turn 1 dispatches through harness §3.1 (new-session,
empty history); turn 2 dispatches through harness §3.2 (existing-active-
session, non-empty history). The chat harness loads the prior turn's
history before invoking on turn 2.

**Spec sections exercised:**

- harness-chat §4 — conversation history convention
- harness-chat §6 — inbound dispatch path classification
- harness §3.1 — new-session inbound dispatch path
- harness §3.2 — existing-active-session inbound dispatch path

**What passes:**

- Turn 1 dispatch path is §3.1; turn 2 dispatch path is §3.2.
- After turn 1: session `messages` count is 2 (user + assistant).
- After turn 2: session `messages` count is 4 (user1 + assistant1 + user2 +
  assistant2) in append order.
- Turn 2's `.replies` contains only the new assistant message (not turn 1's
  messages).

**What fails:**

- Turn 2 dispatches through §3.1 — would mean the path-classification rule
  isn't reading the session's existing history.
- Turn 2's `.replies` contains turn 1's messages — §7's tail extraction
  rule isn't tracking the pre-invoke history length correctly.
- Session `messages` count is wrong after either turn — append reducer not
  composing correctly.
