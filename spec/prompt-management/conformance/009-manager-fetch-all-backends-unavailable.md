# 009 — Manager Fetch All Backends Unavailable

Composite manager with two backends, both raising
`prompt_store_unavailable`. The manager MUST consult both in order
and then raise `prompt_store_unavailable` (per §8: "After exhausting
all backends with prompt_store_unavailable, the manager raises
prompt_store_unavailable to the caller").

**Spec sections exercised:**

- §8 Composite backends and fallback — exhaust-all-then-raise behavior
  on universal infrastructure failure.
- §6 PromptManager.fetch() — propagates infrastructure failure only
  when no backend succeeds.

**What passes:**

- The manager raises `prompt_store_unavailable`.
- Both backends' `fetch()` were invoked exactly once.

**What fails:**

- The manager raises a different error category.
- The manager raises after only one backend's fetch (didn't try the
  second).
- The manager returns successfully — impossible since both backends
  failed, but would indicate stale-state leakage.
