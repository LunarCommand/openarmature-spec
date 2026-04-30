# 021 — Fan-Out with Instance-Middleware Retry

Verifies §9.7 `instance_middleware` semantics: retry middleware wrapping each instance's whole
subgraph invocation re-runs the entire subgraph (fresh state, every inner node re-executes) on
failure. This is the seam for retries that span multiple inner nodes — node-level retry alone
couldn't recover here because the failure occurs in stage_b after stage_a has already
mutated state.

**Spec sections exercised:**

- §9.7 Instance middleware — wraps each instance's invocation as a unit.
- §9.7 Composition with `error_policy: fail_fast` — instance-middleware retry exhaustion
  propagates as a single instance failure, which fail-fast then turns into fan-out cancellation.
- §6.1 Retry — applied at the instance boundary instead of at an individual node.

**Cases:**

1. `instance_middleware_retry_succeeds` — `max_attempts: 3`. Each instance fails once on its
   whole-invoke (stage_b raises), retry middleware re-invokes the subgraph from scratch (stage_a
   runs again, stage_b runs again, succeeds this time). Final `results == [7, 9]`.
2. `instance_middleware_retry_exhausts_then_fail_fast` — `max_attempts: 1` (no retry budget).
   First instance's first attempt fails, retry exhausts immediately, fail_fast cancels the other
   instance, fan-out raises `node_exception`.

**What passes:**

- Case 1: final state has both items processed; the inner subgraph re-ran from scratch on retry
  (the harness MAY assert stage_a fired twice per instance via observer events).
- Case 2: engine raises `node_exception`; sibling instance was cancelled.

**What fails:**

- Case 1: only the second invocation's effects show — retry didn't actually re-run the whole
  subgraph (e.g., it only retried stage_b without re-running stage_a).
- Case 2: fan-out doesn't raise — instance-middleware retry's exhaustion didn't propagate to
  fail-fast.
