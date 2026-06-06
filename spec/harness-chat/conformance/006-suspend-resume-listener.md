# 006 — Suspension-resume via subscribed listener (§8.2)

After the suspending turn (using fixture 005's two-node compose-then-suspend
pattern), a signal arrives via the harness signal coordinator. The
post-resume assistant reply fires through a **subscribed listener** the
caller registered against the chat harness (per the
chat-UX-is-asynchronous-post-suspend rationale §8.2 ratifies as the
default). The third graph node (`post_resume`) runs after the resume
invoke and appends the final reply.

The fixture verifies that the listener-based path is the load-bearing
delivery mechanism — the user does NOT have to send another message to
receive the post-resume reply.

**Spec sections exercised:**

- harness-chat §8.2 — signal-resume flow + subscribed-listener primitive
- harness §3.3 — signal-resume inbound dispatch path
- harness §6 — signal coordinator
- suspension §7 — resume operation

**What passes:**

- Turn 1 returns `ChatTurnOutcome.suspended` with the pending message and
  signal descriptor.
- The signal arrives with `payload: {approved: true}`.
- The resumed invocation runs `post_resume` and appends an assistant
  "Email sent." message.
- The listener callback fires exactly once with `ChatTurnOutcome.completed`
  carrying the post-resume reply.
- A subsequent `send()` on the same session does NOT receive the
  post-resume reply (the listener already consumed it).

**What fails:**

- The listener doesn't fire after resume — would mean the §8.2 listener
  contract is broken.
- The listener fires more than once for the same resumed turn — would
  mean the once-per-resumed-turn invariant is broken.
- A subsequent `send()` returns the post-resume reply (without an opt-in
  to the synchronous-next-`send()` alternative) — would mean the default
  delivery path is wrong.
