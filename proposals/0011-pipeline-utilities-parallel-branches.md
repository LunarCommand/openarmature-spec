# 0011: Pipeline Utilities — Parallel Branches

- **Status:** Draft
- **Author:** Chris Colinsky
- **Created:** 2026-05-06
- **Targets:** spec/pipeline-utilities/spec.md (adds §11), spec/graph-engine/spec.md (§3 concurrency exception, §6 NodeEvent `branch_name`)
- **Related:** 0001, 0002, 0003, 0004, 0005
- **Supersedes:**

## Summary

Add a normative **parallel branches** primitive to pipeline-utilities §11 — a node that
dispatches **M heterogeneous compiled subgraphs concurrently** within a single parent
invocation. Each branch is a separately compiled subgraph with potentially different state
schema, different middleware, and different topology; per-branch projection in (`inputs`) and
out (`outputs`) lets each branch read and write parent-state fields. Complements the §9
fan-out primitive (data-driven, N instances of one subgraph) with a topology-driven primitive
(M instances of M different subgraphs).

## Motivation

Fan-out (§9) addresses the **data-driven** case: N items, one subgraph, instantiated N times.
The **topology-driven** case — running M heterogeneous workflows concurrently — has no
normative primitive today. Examples that surface repeatedly:

1. **Multi-source research.** Hit Wikipedia, an internal vector store, and a web search API in
   parallel; synthesize the three result sets downstream. Each source has a different
   subgraph (different state shape, different middleware, different LLM provider).
2. **Multi-model parallel inference.** Send the same prompt to Claude, GPT-4, and Gemini
   concurrently; compare or vote on responses. Each provider's subgraph has its own
   error-handling middleware and retry policy.
3. **Parallel validation.** On a single input, run schema validation, security scanning, and
   type checking concurrently. Each validator has independent dependencies and side effects.
4. **Heterogeneous tool dispatch in a tool-calling agent.** Fire three different tool calls
   in parallel rather than waiting for the LLM to sequence them serially.

Today users work around this by writing a "dispatcher subgraph" with conditional routing on
some discriminator field, packing M workflows into one subgraph. This works when the M
workflows share a state shape. It breaks down when they genuinely need different state
schemas — forcing users to either (a) widen one shared schema to a union of all M shapes
(awkward, type-unsafe), or (b) write a regular node that does its own `asyncio.gather` and
loses §6 observer events, `fan_out_index` attribution, §9.5 error policies, and §9.7 instance
middleware.

The proposed primitive gives the topology-driven case the same first-class treatment fan-out
gives the data-driven case.

## Detailed design

### Pipeline-utilities §11: Parallel branches

A **parallel branches** node holds a mapping from branch name to **branch spec**. At dispatch
time, the engine projects parent state into each branch's per-branch state via `inputs`,
runs all branches concurrently (with optional per-branch middleware), and projects each
branch's exit state back into parent state via `outputs`. Different branches MAY write
different parent fields; when two branches write the same parent field, the parent's
reducer for that field merges the contributions per its semantics.

#### 11.1 Configuration

A parallel-branches node carries:

- `branches` — a mapping from `branch_name` (non-empty string) to a **branch spec** (§11.1.1).
  Insertion order is preserved and is the order observer events for branch dispatch fire,
  regardless of completion timing (§11.8).
- `error_policy` — one of `"fail_fast"` (default) or `"collect"`. Same semantics as §9.5.
- `errors_field` — optional parent state field name receiving per-branch errors when
  `error_policy: "collect"`. Implementation-defined record shape; SHOULD include the failing
  `branch_name` and the error category.

##### 11.1.1 Branch spec

Each branch spec carries:

- `subgraph` — a compiled subgraph reference. Different branches MAY reference different
  compiled subgraphs with different state schemas.
- `inputs` — optional mapping `subgraph_field → parent_field` (same shape as proposal 0002
  subgraph `inputs`). At branch entry, each named subgraph field is initialized from the
  named parent field. Subgraph fields not in `inputs` use the subgraph's declared defaults.
- `outputs` — optional mapping `parent_field → subgraph_field` (same shape as proposal 0002
  subgraph `outputs`). At branch exit, each named parent field receives the named subgraph
  field's exit value, merged via the parent's reducer for that field.
- `middleware` — optional list of middlewares wrapping the whole branch invocation as a unit
  (§11.7). Heterogeneous across branches — branch A's middleware MAY differ from branch B's.

#### 11.2 Per-branch projection (in)

At dispatch entry, each branch's initial subgraph state is constructed by:

1. Starting from the branch's subgraph schema's declared field defaults.
2. Overlaying `inputs` mappings: each subgraph field named on the LHS is set to the value of
   the corresponding parent field on the RHS, read from the parent state at dispatch time.

The mapping is the same shape as proposal 0002's subgraph `inputs`. References to undeclared
subgraph fields or undeclared parent fields are compile-time errors per proposal 0002 §2's
`mapping_references_undeclared_field` category.

#### 11.3 Concurrent execution

All branches dispatch simultaneously when the engine enters a parallel-branches node. This is
the second exception to graph-engine §3's single-threaded execution rule (alongside §9
fan-out's first exception); single-threaded execution resumes for the parent run after the
parallel-branches node completes.

This proposal does NOT include a configurable concurrency bound. The number of branches M is
expected to be small (typically 3–10), and per-branch concurrency tuning is rare in practice.
A future proposal MAY add a `concurrency` knob if real workloads demonstrate the need.

#### 11.4 Per-branch projection (out)

When a branch's subgraph finishes (END node reached), the engine constructs a per-branch
**contribution** — a mapping `parent_field → exit_value` built from the branch's `outputs`
mapping (each named subgraph field is read from the branch's exit state). Subgraph fields
not named in `outputs` are discarded (matching proposal 0002 outputs semantics).

Contributions are **buffered**; no parent-state merging happens incrementally on branch
completion. When the parallel-branches node itself completes (all branches succeeded under
`fail_fast`, or `collect` ran to completion), the engine applies all buffered contributions
to parent state in **branch insertion order** (§11.8), using each parent field's reducer for
that field. This mirrors §9.3 fan-in: contributions are collected during dispatch and merged
deterministically once at node completion.

When two or more branches write the same parent field via `outputs`, the parent's reducer
applies the contributions in branch insertion order. For `last_write_wins` reducers, this
means the last-listed branch wins. For `append` reducers, contributions are appended in
branch order. For `merge` reducers, later branches' keys override earlier ones.

Authors choosing parent fields and reducers SHOULD design for the merge semantics they want.
A common pattern is using `merge` for fields multiple branches contribute to (each branch
writes its own keys) or `last_write_wins` with branches that write disjoint fields.

#### 11.5 Error policy

Same shape as §9.5. Behavior at runtime:

- **`fail_fast` (default).** First branch failure cancels every still-running branch (via the
  host language's idiomatic cancellation primitive — Python `asyncio.Task.cancel()`,
  TypeScript `AbortController`, etc.). The parallel-branches node raises a wrapped
  `node_exception` carrying the failing branch's exception as `__cause__`. Per §11.4's
  collect-then-apply semantics, no branch contributions have been applied to parent state at
  this point; the buffered contributions are discarded. `recoverable_state` is therefore the
  parent state at the moment the parallel-branches node entered — matching §9.5's fan-out
  fail_fast.
- **`collect`.** All branches run to completion regardless of individual failures. Successful
  branches' contributions merge per §11.4. Failed branches' errors are recorded in
  `errors_field` (when configured); their `outputs` projections do NOT fire. The node returns
  normally; the parent run continues.

Implementations MAY surface partial-completion telemetry (which branches succeeded, which
failed) via observer events (§6).

#### 11.6 Composition with parent middleware

Per-graph and per-node middleware applied to the parallel-branches node wrap it as a SINGLE
dispatch — exactly mirroring §9.6's contract for fan-out. From the parent's middleware view,
the parallel-branches node looks like any other node: one `started` event, one `completed`
event around the whole operation. The parent's retry middleware, if any, retries the whole
parallel-branches node (re-dispatching all M branches), not individual branches.

Per-branch internal events (the branches' subgraph nodes' started/completed pairs) come from
the branches' subgraph executions and carry the new `branch_name` field (§11.7,
graph-engine §6).

#### 11.7 Branch middleware

Each branch's `middleware` (§11.1.1) wraps the branch's entire subgraph invocation as a unit
— directly mirroring §9.7's `instance_middleware` contract. The branch's whole subgraph runs
inside the middleware chain; failures in any inner node propagate up to the branch's
middleware. Retry middleware applied at the branch level retries the whole branch's subgraph.

Branch middleware composition is heterogeneous. Branch A may have `[retry, timing]`; branch B
may have `[]`; branch C may have `[custom_breaker]`. Each branch's chain is independent.

#### 11.8 Determinism

The branch dispatch order — and therefore the order branches' `started` events fire on the
§6 observer stream — is the **insertion order of the `branches` mapping**. This holds
regardless of which branch's first inner node finishes first.

Branch fan-in (§11.4) is deterministic: when two branches write the same parent field, the
reducer applies their contributions in branch insertion order, not completion order.

This preserves graph-engine §5's "same input → same output" determinism guarantee through the
parallel-branches primitive: scheduler nondeterminism affects timing but not state.

### Cross-spec touchpoints

- **Graph-engine §3** (Execution model — concurrency exception). A second exception is added
  alongside fan-out's: the parallel-branches node may execute multiple subgraphs concurrently.
  Single-threaded execution resumes for the parent run after the parallel-branches node
  completes.
- **Graph-engine §6** (Observer hooks — node event shape). A new optional `branch_name`
  field is added — a non-empty string, populated only on events from nodes inside a
  parallel-branches branch. The combination of `namespace`, `branch_name`, `fan_out_index`,
  `attempt_index`, and `phase` uniquely identifies an event source; any of `branch_name` /
  `fan_out_index` MAY be absent depending on the surrounding topology, and both MAY be
  present simultaneously when a fan-out node executes inside a parallel-branches branch
  (and vice versa).
- **Pipeline-utilities §6** (Canonical middleware). Branch middleware reuses the §6
  middleware seam — no new middleware shape; the existing `(state, next) -> partial_update`
  Protocol applies.
- **Pipeline-utilities §9** (Parallel fan-out). Fan-out and parallel branches compose: a
  branch's subgraph MAY contain a fan-out node, and a fan-out instance's subgraph MAY contain
  a parallel-branches node. Each operates independently; their respective concurrency
  exceptions stack.
- **Pipeline-utilities §10** (Checkpointing — when implemented). The parallel-branches node
  fires §6 events that the §10 Checkpointer captures per its existing rules. v1 atomic-restart
  semantics for fan-out (§10.7) apply analogously to parallel branches: a crash mid-dispatch
  re-runs the whole parallel-branches node on resume. Per-branch resume is deferred to a
  follow-on alongside per-instance fan-out resume (proposal 0009).

### New error categories

- `parallel_branches_no_branches` — compile error. The `branches` mapping is empty.
  Non-transient.
- `parallel_branches_branch_failed` — runtime category. Raised by the engine when a branch's
  subgraph raises under `error_policy: "fail_fast"`. Wraps the inner exception as `__cause__`;
  carries the failing `branch_name` as a structured field. Non-transient by default;
  inherits transient classification from the wrapped exception per pipeline-utilities §6.1.

Existing categories that compose:

- `mapping_references_undeclared_field` (proposal 0002) — raised at compile time when an
  `inputs` or `outputs` mapping in a branch spec names a field not declared on the relevant
  side.
- `node_exception` (graph-engine §4) — the `parallel_branches_branch_failed` category is a
  `node_exception` subtype attached at the parallel-branches node's level.

## Conformance test impact

### New fixtures: pipeline-utilities

- **`0NN-parallel-branches-basic.yaml`** — three heterogeneous branches with different state
  shapes; each writes a different parent field; assert all three branches run concurrently
  and their contributions land in parent state.
- **`0NN+1-parallel-branches-fail-fast.yaml`** — three branches; the second fails after the
  first has succeeded; assert `recoverable_state` equals the pre-entry parent-state snapshot
  (none of the branches' contributions visible, including the first's), the still-running
  third branch is cancelled, and the parallel-branches node raises
  `parallel_branches_branch_failed`.
- **`0NN+2-parallel-branches-collect.yaml`** — three branches; one fails; assert the two
  successful branches' contributions merge into parent state, the failure is recorded in
  `errors_field`, and the parent run continues.
- **`0NN+3-parallel-branches-different-state-schemas.yaml`** — three branches with three
  distinct subgraph state schemas (no shared fields); verifies the engine handles
  schema-heterogeneous branches without coercing to a shared schema.
- **`0NN+4-parallel-branches-with-branch-middleware-retry.yaml`** — one branch wraps its
  subgraph with retry middleware; the branch's subgraph raises a transient on first attempt,
  succeeds on second; assert per-branch retry works without affecting the other branches.
- **`0NN+5-parallel-branches-determinism.yaml`** — three branches with deliberately
  randomized completion timing (sleep stubs); assert observer event order matches branch
  insertion order, NOT completion order; assert the merged parent field (when two branches
  write the same field via `merge` reducer) reflects branch insertion order.
- **`0NN+6-parallel-branches-compose-with-fan-out.yaml`** — a branch's subgraph contains a
  fan-out node; verifies composition; observer events from inside the fan-out inside the
  branch carry both `branch_name` and `fan_out_index`.

### New fixtures: graph-engine

- **`0NN-observer-branch-name.yaml`** — verifies the new `branch_name` field on observer
  events fires from nodes inside a parallel-branches branch and is absent on outermost-graph
  events.

(Fixture numbering deferred until proposals 0009 and 0010 are Accepted with finalized
fixture numbering; this proposal's accept PR will pick the next available slot.)

## Alternatives considered

### Don't add a primitive; document the dispatcher-subgraph workaround

Rejected. Works for branches that share a state shape, fails when branches need genuinely
different state schemas (the entire motivation). Forces a wide union schema or asyncio.gather
that loses §6 observer attribution.

### Extend §9 fan-out to support per-instance subgraph selection

Rejected. Conflates two distinct concepts: fan-out is data-driven (N items, count derived
from data); parallel branches is topology-driven (M branches declared statically). Bolting
per-instance subgraph onto fan-out breaks `items_field`'s "items[i] projects to instance i"
semantics. Two primitives is clearer than one overloaded one.

### Make branches dynamic (callable returning the active branch set)

Rejected for v1. Useful but increases complexity (resolving branches at dispatch time,
validating `inputs`/`outputs` against potentially-not-present branches). Defer to a follow-on
when concrete demand surfaces. Static branches at graph-build time cover the documented use
cases (multi-source research, multi-model parallel, parallel validation).

### Use integer `branch_index` instead of string `branch_name`

Rejected. Names are descriptive (`"web_search"` vs. `0`) and match the per-branch
heterogeneity better than indices. Observer attribution by name is more useful in trace UIs.

### Require all branches to share a state schema

Rejected. The whole point of the primitive is to handle the heterogeneous-schema case the
dispatcher-subgraph workaround can't. Same-schema branches CAN use this primitive but should
not be forced to.

## Open questions

- **Branch ordering source.** Proposal uses dict insertion order. Should the spec require an
  explicit ordering field on branches (a list of `(name, spec)` tuples instead of a dict) for
  languages whose dicts don't preserve order? Lean: spec mandates insertion-order semantics
  but allows implementations to use any equivalent shape.
- **Cancellation precision under `fail_fast`.** When branch A fails, branches B and C are
  cancelled. If branch B's subgraph was mid-checkpoint-save (per proposal 0008 §10.3), does
  the cancellation interact with checkpointing? Likely the same answer as §9.5 fail-fast +
  checkpointing — need to verify when both proposals are accepted.
- **Concurrency bound.** Should there be a configurable bound? Lean: defer; M is small in
  practice.
- **Top-level timeout.** Should the parallel-branches node accept a timeout that cancels all
  branches if not done by deadline? Lean: defer; users wrap with their own middleware or a
  future timeout middleware proposal.
