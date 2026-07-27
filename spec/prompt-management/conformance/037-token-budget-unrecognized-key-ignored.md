# 037 — unrecognized `token_budget` config key is ignored (apply-recognized-and-ignore)

Pins proposal 0109's §5 rule: a backend sourcing `Prompt.token_budget` from a config that carries an
unrecognized key alongside valid bounds **applies the recognized bounds and ignores the unknown key**. Unlike
`sampling`, `token_budget` has no extras mapping, so a stray key is dropped rather than carried through — the
convergent, forward-compatible behavior (a future/vendor key doesn't invalidate a well-formed budget). And the
fetch succeeds: an advisory `token_budget` config never breaks the call (§3).

**Spec sections exercised:**

- prompt-management §5 (proposal 0109) — unrecognized-key handling converges to apply-recognized-and-ignore; a
  malformed/unrecognized `token_budget` config MUST NOT break the call.
- prompt-management §3 — `token_budget` is advisory / observability-only.

**Case:**

1. `fetch` of a prompt whose sourced `token_budget` config is `{input_max_tokens: 10, unknown: 5}` → the returned
   `Prompt.token_budget` is exactly `{input_max_tokens: 10}` (the `unknown` key dropped), and the fetch completes
   normally.

**What fails:**

- Carrying the `unknown` key through onto `Prompt.token_budget`, rejecting the whole budget to fallback (the
  divergent behavior 0109 converges away), or letting the unrecognized key break the fetch / call.
