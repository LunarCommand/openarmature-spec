# 017 — Content Blocks System Message Text-Only

A `system` message with `content` as a content-block sequence MUST be
rejected at pre-send validation with `provider_invalid_request`. In v1,
only `user` messages support content-block sequences per the amended §3
per-role constraints. The system, assistant, and tool roles remain
text-string-only.

**Spec sections exercised:**

- §3 Message shape — per-role constraints. Only the `user` row was
  amended to accept content-block sequences in this proposal; `system`
  remains `content` MUST be a non-empty string.
- §7 — `provider_invalid_request` raised when per-role constraints are
  violated.

**What passes:**

- The implementation raises `provider_invalid_request` because the
  system message's `content` is not a non-empty string.

**What fails:**

- The system message with block content reaches the wire — would mean
  the per-role constraint was relaxed for all roles, not just `user`.
- A different error category is raised (e.g., the implementation
  invented a new category for "wrong role"). The §3 constraint maps
  directly to `provider_invalid_request`.
