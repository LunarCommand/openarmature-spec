# 119 — Callable-branch dispatch-span attempt_index under node-level retry

Verifies that a callable-branch parallel-branches node under **node-level retry** reports the
dispatching node's **current** `attempt_index` on its synthetic callable-branch events (graph-engine
§6) — so the OTel observer renders the retry attempt's callable-branch dispatch span with
`openarmature.node.attempt_index = 1` (§5.2 / §5.7), not a hard-coded `0`. This pins the
attempt-index dimension of the §5.7 callable-branch dispatch span that proposal 0075 left unfixtured
(fixture 110 covers the single-attempt span shape and skip-emits-no-span). It is the callable-branch
analogue of fixture 007 (per-attempt sibling node spans disambiguated by
`openarmature.node.attempt_index`).

**Spec sections exercised:**

- graph-engine §6 — the inline-callable branch's **synthetic** `started`/`completed` pair (the
  callable is the event-source unit, keyed by `branch_name`); `attempt_index` propagates the
  wrapping retry's current attempt index to events from anything re-executed as part of the retried
  unit (the parallel-branches node).
- observability §5.2 — `openarmature.node.attempt_index` (the §6 `attempt_index` field) on node
  spans.
- observability §5.7 — the inline-callable branch's per-branch dispatch span (no inner-node spans
  beneath it).
- observability §4.3 *Parallel-branches dispatch span synthesis* — the NODE span and each per-branch
  dispatch span are keyed on the §6 event-source identity tuple **including `attempt_index`**, so
  each retry attempt produces a distinct sibling NODE span with its own dispatch spans.
- pipeline-utilities §11.6 — node-level (parent-node) retry on a parallel-branches node retries the
  whole node, re-dispatching all branches.
- pipeline-utilities §11.9 — a `call` branch's transient failure wraps as
  `parallel_branches_branch_failed` (a `node_exception` subtype inheriting the wrapped exception's
  transient classification), which the node-level retry classifier matches.

**Cases:**

1. `callable_branch_dispatch_span_carries_attempt_index_one_on_node_retry` — node `retrieve` with
   callable branches `vector` (a `flaky` callable: transient on attempt 0, succeeds on attempt 1) and
   `fts` (always succeeds), wrapped by node-level retry on the parallel-branches node itself
   (`max_attempts` 2, transient classifier on `provider_rate_limit`). Attempt 0's `vector` callable
   raises a transient, failing the whole node under `fail_fast`; the node-level retry re-dispatches
   both branches on attempt 1, where `vector` succeeds. The OTel observer renders two sibling
   `retrieve` NODE spans (attempt 0 ERROR, attempt 1 OK), each with callable-branch dispatch spans
   carrying that attempt's `openarmature.node.attempt_index`.

**What passes:**

- Two sibling `retrieve` parallel-branches NODE spans, one per attempt, disambiguated by
  `openarmature.node.attempt_index` (0 then 1).
- The attempt-0 `vector` dispatch span carries `attempt_index = 0` and ERROR; the attempt-1
  `vector`/`fts` dispatch spans carry `attempt_index = 1` and OK.
- The synthetic callable-branch `started` AND `completed` events on the retry attempt both report
  `attempt_index = 1` (sourced from the node's current attempt counter, not hard-coded).

**What fails:**

- The retry attempt's callable-branch dispatch span carries `attempt_index = 0` (the §6 synthetic
  callable-branch event hard-coded `attempt_index` to 0 instead of reporting the node's current
  attempt index).
- Only one `retrieve` NODE span is rendered (the per-attempt dispatch-span synthesis collapsed the
  two attempts instead of keying on `attempt_index`).
- The node-level retry retried individual branches rather than re-dispatching the whole node
  (contradicting §11.6).
