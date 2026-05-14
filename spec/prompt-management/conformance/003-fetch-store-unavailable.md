# 003 — Fetch Store Unavailable

A backend simulating infrastructure failure (network unreachable,
filesystem I/O error, vendor API timeout, etc.) MUST raise
`prompt_store_unavailable`. Distinct from `prompt_not_found`: the
prompt may exist but the backend can't reach it right now.

**Spec sections exercised:**

- §5 PromptBackend — "fetch() MUST raise prompt_store_unavailable
  when the backend is unreachable."
- §10 — `prompt_store_unavailable` is transient; same fetch may
  succeed when the backend recovers.

**What passes:**

- `fetch()` raises `prompt_store_unavailable`.

**What fails:**

- `prompt_not_found` is raised — would conflate infrastructure failure
  with logical absence (§8 fallback semantics depend on the
  distinction).
- The fetch returns successfully despite the simulated outage.
