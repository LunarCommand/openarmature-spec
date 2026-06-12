# 064 — Failure-isolation cause fidelity at carrier-wrapper sites

Verifies §6.3's *Cause fidelity at carrier-wrapper sites* clause (proposal 0065). When
`FailureIsolationMiddleware` runs at a non-node placement — §9.7 instance middleware or §11.7
branch middleware — the engine has already wrapped the originating error as a graph-engine §4
`node_exception` before the isolation middleware catches it. `caught_exception.category` MUST
resolve **through** that carrier wrapper to the originating cause, not report the masking
`node_exception`. This is the same carrier-wrapper resolution §6.1's default classifier already
performs.

**Spec sections exercised:**

- §6.3 — *Cause fidelity at carrier-wrapper sites* (the carrier-wrapper unwrap MUST).
- §9.7 — instance middleware (the wrapping site in Cases 1 and 3).
- §11.7 — branch middleware (the wrapping site in Case 2).
- §6.1 — the carrier-wrapper resolution precedent (a `node_exception` whose `__cause__` is a
  category is classified by that category).

**Cases:**

1. `instance_site_resolves_to_originating_category` — a single-instance fan-out whose instance
   raises `provider_unavailable` on every attempt, with `instance_middleware = [failure_isolation,
   retry]` (isolation outer, retry inner). Retry exhausts; failure isolation catches the
   instance's `node_exception` and degrades. Asserts `caught_exception.category ==
   provider_unavailable` — resolved through the carrier wrapper, **not** `node_exception`.
2. `branch_site_resolves_to_originating_category` — a parallel-branches node with one branch whose
   `middleware = [failure_isolation, retry]`; the branch's inner node raises `provider_unavailable`.
   Asserts the category resolves through the branch's `node_exception` to `provider_unavailable`.
   (Note: at the §11.7 branch-middleware site the caught wrapper is the branch's plain
   `node_exception`; the engine's `parallel_branches_branch_failed` wrapper is raised at the
   parallel-branches *node* level per §11.9 and is the parent-node (§11.6) site's concern, not
   branch middleware's.)
3. `instance_site_uncategorized_cause_is_null` — the originating cause is a bare exception with no
   category. Resolving through the carrier wrapper reaches a cause with no category, so
   `caught_exception.category == null` per §6.3's existing uncategorized rule.

**What passes:**

- At both wrapping sites the reported category is the originating cause's, not `node_exception`.
- The catch/degrade behavior is unchanged — each case completes with the degraded update.
- An uncategorized originating cause yields `category == null`.

**What fails:**

- `caught_exception.category` reports `node_exception` at a wrapping site (the pre-0065 masking
  behavior — the carrier wrapper was not resolved).
- The category reports a wrapper category (`parallel_branches_branch_failed`) instead of resolving
  to the originating cause.

**Out of strict scope (SHOULD, not asserted here):**

- **Message coherence** — §6.3 SHOULDs that `caught_exception.message` track the resolved cause;
  asserted informally (the cases omit a strict message expectation so a category-MUST-only
  implementation still conforms).
- **Wrapped lineage** — §6.3 SHOULDs that the event's `fan_out_index` / `branch_name` / `namespace`
  resolve to the wrapped instance / branch; not strictly asserted, since recovering the identity
  may require an engine change.
- **Node-level placement** — already faithful and covered by fixture 061
  (`caught_exception.category == provider_unavailable` at node level); not duplicated here.
