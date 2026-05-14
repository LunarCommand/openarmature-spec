# 024 — Structured Output Non-Transient Classification

Verifies §7's "non-transient by default" classification for
`structured_output_invalid`. The default pipeline-utilities
`RetryMiddleware` classifier MUST NOT match this category to the
transient set; retrying a schema-noncompliant response without changing
the prompt/model/schema typically fails the same way and wastes tokens.

**Spec sections exercised:**

- §7 retry classification — `structured_output_invalid` is in the
  non-transient list.
- §7 user opt-in — users wanting retry semantics MAY add the category
  to their RetryMiddleware classifier's transient set (this fixture
  tests the *default*; opt-in is covered by user-level tests, not
  here).

**What passes:**

- `complete()` raises `structured_output_invalid`.
- The provider mock is invoked exactly once (no retry).

**What fails:**

- The provider mock is invoked more than once — would mean the default
  classifier included `structured_output_invalid` in the transient set
  (would cause unnecessary retries and token waste).
- A different error category is raised.
