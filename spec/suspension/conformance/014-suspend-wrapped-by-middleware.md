# 014 — Middleware wrapping a suspending node

Middleware MAY wrap a suspending node. The middleware's pre-`next()`
block runs normally; the middleware's post-`next()` block does NOT
run when the inner node suspends (since `next()` does not return — it
raises a typed internal control-flow exception or returns a sentinel,
per implementation).

**Spec sections exercised:**

- §8.4 — middleware composition with suspending nodes: pre-`next()`
  runs; post-`next()` skipped on the suspending attempt.

**What passes:**

- The middleware log captures the pre-`next()` marker
  (`"entered_pre"`) — confirming the middleware ran its pre-phase.
- The middleware log does NOT contain the post-`next()` marker
  (`"entered_post"`) — confirming the post-phase was skipped because
  the inner node suspended.

**What fails:**

- The post-`next()` marker appears in the log — would mean the
  middleware's post-phase executed despite the inner suspension,
  violating the §8.4 contract.
- The pre-`next()` marker is missing — would mean the middleware did
  not run at all (the suspending node bypassed the middleware chain).
