# 036 — Parallel Branches With Branch Middleware Retry

Three branches; branch alpha wraps its subgraph with retry middleware.
Alpha's inner node fails first attempt with a transient exception,
succeeds on the second. Branches beta and gamma complete normally on first
try. Verifies §11.7 branch middleware operates per-branch without affecting
sibling branches.

**Spec sections exercised:**

- §11.7 Branch middleware — per-branch middleware list wraps the branch's
  subgraph as a unit; middleware composition is heterogeneous across
  branches (alpha has retry, beta and gamma have none).
- §11.1.1 Branch spec — `middleware` field on the branch spec.
- §6.1 Retry middleware (transitively, via branch composition) — retry
  classifier matches the transient `provider_rate_limit` category.
- §11.4 Per-branch projection (out) — alpha's contribution lands once
  the retry succeeds (not the failed attempt).

**What passes:**

- Final state: alpha_result=1, beta_result=2, gamma_result=3.
- Alpha's inner node fires events for `attempt_index=0` (failed) and
  `attempt_index=1` (succeeded) — two observer event pairs.
- Beta and gamma each fire one event pair (no retry).
- The graph completes (alpha's transient was caught and retried).

**What fails:**

- Alpha runs only once (retry middleware not engaged).
- Alpha's first-attempt failure propagates (retry classifier not matching
  the transient category).
- Beta or gamma is affected by alpha's retry (e.g., they re-run too).
- alpha_result reflects the failed-attempt state (would mean the
  contribution buffer captured the wrong attempt's exit).
